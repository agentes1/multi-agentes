# API & Pipeline Review

**Files reviewed:** `api.py`, `pipeline.py`
**Date:** 2026-04-14
**Reviewer:** automated code-review agent

---

## api.py

### Purpose

Thin HTTP façade over the pipeline. Exposes a single business endpoint (`POST /process`) and a liveness probe (`GET /health`). It is responsible for:
- Deserializing incoming JSON into typed Pydantic models
- Delegating all logic to `run_pipeline`
- Mapping business-level errors to HTTP 400 responses
- Auto-generating OpenAPI docs via FastAPI

### Endpoints

| Method | Path | Description | Request body | Response |
|--------|------|-------------|--------------|----------|
| POST | `/process` | Run the full two-agent pipeline | `{ source_input: dict, thread_id?: str }` | `ProcessResponse` (see schema below) |
| GET | `/health` | Liveness check | — | `{ status: "ok" }` |

**ProcessResponse schema:**

| Field | Type | Notes |
|-------|------|-------|
| `ok` | bool | True on success |
| `thread_id` | str \| None | Echo of the input thread_id |
| `stage` | str \| None | Agent name if failure |
| `error` | str \| None | Error message if failure |
| `validation_notes` | list[str] | Non-blocking warnings from intake_agent |
| `normalized_request` | dict | Output of intake_agent |
| `quote_result` | dict | Output of budget_agent |
| `final_text` | str | Human-readable quote |

### Error handling

- Pydantic validates request shape automatically; malformed JSON returns 422.
- Business errors from the pipeline (`ok=False`) are raised as `HTTPException(400)` with the full result dict as `detail` — client receives a structured JSON error body.
- No explicit try/except around `run_pipeline`; unhandled exceptions (network timeouts, agent crashes, etc.) will surface as unformatted 500s.

### Issues Found

| ID | Severity | Description |
|----|----------|-------------|
| A-1 | **CRITICAL** | `allow_origins=["*"]` with `allow_methods=["*"]` and `allow_headers=["*"]` is a fully open CORS policy. Any website can call this API with credentials. Restrict to known origins in production. |
| A-2 | **HIGH** | No authentication or authorization on any endpoint. `POST /process` can be called by anyone who can reach the server. Add at minimum an API-key header check or OAuth2 bearer token. |
| A-3 | **HIGH** | `run_pipeline` is not wrapped in a try/except. An uncaught exception (e.g., import error in an agent, network timeout calling an LLM) returns a raw 500 with a Python traceback potentially visible in logs or to the caller. Add a top-level `except Exception` that maps to a sanitized 500 and logs the full traceback internally. |
| A-4 | **MEDIUM** | `ProcessResponse` always includes `thread_id: None` because the pipeline result dict (returned by `run_pipeline`) never sets `thread_id`. The field is silently dropped on success. If session tracking is needed, `run_pipeline` should echo it back, or the API layer should inject it before returning. |
| A-5 | **MEDIUM** | `source_input` is typed as `dict` (unvalidated free-form object). No schema is enforced at the boundary; downstream agents bear the full validation burden. Consider a typed sub-model (e.g., `SourceInput`) to fail fast with useful error messages. |
| A-6 | **LOW** | `uvicorn.run(..., reload=True)` is hardcoded. `reload=True` must never run in production (it disables worker isolation). Guard behind an env-var flag or remove and rely on the process manager. |
| A-7 | **LOW** | No request-level logging (request ID, timestamp, duration). Difficult to correlate errors in production without it. |

---

## pipeline.py

### Purpose

Sequential two-agent orchestrator. It:
1. Accepts raw input from any channel
2. Runs `intake_agent` to normalise and validate the request
3. If valid, runs `budget_agent` to produce a quote
4. Returns a structured dict consumed by `api.py`

It is the only place where agent graphs are wired together.

### Data flow (step by step)

```
Caller
  │
  ▼
run_pipeline(source_input, thread_id, model?)
  │
  ▼ [Step 1]
intake_graph.ainvoke({ source_input })
  config: { deps: build_intake_deps(model) }
  │
  ├─ error? → return { ok: False, error: ... }
  │
  ▼ [Step 2]
budget_graph.ainvoke({ normalized_request })
  config: { deps: build_budget_deps(model), thread_id: thread_id }
  │
  ├─ error? → return { ok: False, error: ... }
  │
  ▼ [Success]
return {
  ok: True,
  normalized_request: intake_result["normalized_request"],
  quote_result:       budget_result["quote_result"],
  final_text:         budget_result["final_text"],
}
```

**Inter-agent contract:**
- `intake_agent` output key used: `normalized_request`
- `budget_agent` input key expected: `normalized_request`
- `budget_agent` output keys used: `quote_result`, `final_text`

### Issues Found

| ID | Severity | Description |
|----|----------|-------------|
| P-1 | **HIGH** | No try/except around either `ainvoke` call. If an agent graph raises (e.g., LLM API rate-limit, missing dependency, JSON parse error inside a node), the exception propagates uncaught to the caller. The API layer also lacks a catch (see A-3), so the result is an unhandled 500. |
| P-2 | **HIGH** | Agent graphs are rebuilt on every request (`build_intake_graph()`, `build_budget_graph()`). If graph construction is expensive (compilation, schema loading) this is a performance problem at scale. Graphs should be built once at startup and reused (module-level singleton or `@functools.lru_cache`). |
| P-3 | **HIGH** | `build_intake_deps(model=model)` and `build_budget_deps(model=model)` are called on every request too. If `model` is `None` (the default for all API calls since `api.py` never passes it), both agents always use their default model. The `model` parameter is dead code from the API path — undocumented and untested. |
| P-4 | **MEDIUM** | Error return on intake failure is `{ ok: False, error: ... }` — missing `stage` field. The `ProcessResponse` schema has a `stage` field specifically to identify which agent failed; it is populated nowhere in `pipeline.py`, so the client can never distinguish an intake failure from a budget failure. |
| P-5 | **MEDIUM** | `thread_id` is threaded through to `budget_agent` but not to `intake_agent`. If `intake_agent` also needs session continuity (e.g., multi-turn clarification), this is silently dropped. |
| P-6 | **MEDIUM** | No timeout on either `ainvoke` call. A slow or hung LLM call will block the async event loop worker indefinitely. Wrap with `asyncio.wait_for(..., timeout=N)`. |
| P-7 | **LOW** | The function signature has `model: str | None = None` but this is never validated against a list of supported models. A typo in the model name will propagate silently into both agents and fail only at LLM invocation time, far from the entry point. |
| P-8 | **LOW** | No structured logging of pipeline duration, agent outputs (sanitized), or thread_id. Makes production debugging very difficult. |

---

## Cross-cutting observations

- **No authentication anywhere.** The entire system is open to unauthenticated callers. This is the highest priority gap before any production deployment.
- **Implicit contract between agents.** The key names `normalized_request`, `quote_result`, `final_text` are string literals in `pipeline.py` with no shared type definition. A rename in one agent silently breaks the pipeline. Define a typed dataclass or TypedDict as a shared contract.
- **Unhandled exceptions at every layer.** Neither `api.py` nor `pipeline.py` catches exceptions. A single unhandled exception anywhere in the agent graphs produces an unformatted 500 with a potential traceback leak. One try/except in `run_pipeline` and one in the FastAPI route handler would cover both layers.
- **`validation_notes` and `stage` fields are always empty/None on success.** Their population is delegated to agent graphs, but the pipeline result dict never includes them. These fields are in `ProcessResponse` but effectively dead in the current implementation.
- **Graph construction on every request (P-2)** is the most impactful performance issue. Fix it by promoting graph instances to module-level constants in `pipeline.py`.
- **CORS wildcard (A-1) + no auth (A-2)** together mean any browser-based attacker can call the API cross-origin. These must be fixed together.
- **The codebase is clean and minimal** — responsibilities are well separated, the pipeline is easy to follow, and the Pydantic models provide good auto-documentation. The issues above are mostly infrastructure concerns, not design flaws.
