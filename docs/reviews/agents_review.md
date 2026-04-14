# Agents Review

## intake_agent

### Purpose
Receives raw customer input (email, chat, or generic), normalizes it to plain text, uses an LLM to extract a structured JSON request, maps it to an Odoo helpdesk ticket payload, and creates the ticket via XML-RPC. This is the entry point of the pipeline; it classifies every inbound message as `budget`, `issue`, or `discard`.

### State Schema
File: `agents/intake_agent/state.py` — `IntakeState(TypedDict, total=False)`

| Field | Type | Set by |
|---|---|---|
| `messages` | `Annotated[list, add_messages]` | All nodes (append-only via `add_messages` reducer) |
| `source_input` | `dict` | Caller (initial input) |
| `extracted_text` | `str` | `prepare_input_node` |
| `normalized_request` | `dict` | `extract_request_node` |
| `ticket_type` | `str` | `extract_request_node` (`budget`/`issue`/`discard`) |
| `ticket_payload` | `dict` | `prepare_ticket_node` |
| `ticket_id` | `int` | `create_ticket_node` |
| `final_text` | `str` | `create_ticket_node` or `error_node` |
| `error` | `str \| None` | Any node on failure; `None` on success |

- `total=False` means all fields are optional at declaration, which avoids KeyError on partial state but removes static type enforcement for required fields.

### Graph Topology
```
START
  └─► prepare_input_node ──(error?)──► error_node ──► END
                          └──────────► extract_request_node ──(error?)──► error_node ──► END
                                                             └──────────► prepare_ticket_node ──(error?)──► error_node ──► END
                                                                                          └──────────► create_ticket_node ──(error?)──► error_node ──► END
                                                                                                                          └──────────► END
```
- Linear pipeline with four conditional fan-outs to a shared `error_node`.
- No checkpointer — state is not persisted between runs.
- No cycles.

### Key Nodes

- **`prepare_input_node`** — Normalises `email`/`chat`/fallback channels to a single text block. Validates that content is not empty. Returns `extracted_text`.
- **`extract_request_node`** — Sends `extracted_text` to the LLM (single `HumanMessage`). Parses the JSON response, validates all six required keys, normalises `urgency` and `ticket_type` with safe fallbacks, runs requirements through `normalize_requirement` (shared catalog). Returns `normalized_request` and `ticket_type`.
- **`prepare_ticket_node`** — Maps `ticket_type` to hardcoded Odoo team/type/category/tag names. Applies urgency-to-priority mapping (`0`–`2`). Appends tags `Faltan datos` and `Urgente` when applicable. Builds `ticket_payload` dict.
- **`create_ticket_node`** — Resolves all names to Odoo IDs via `OdooAPIWrapper` lookup methods, then calls `create_helpdesk_ticket`. Wraps every Odoo call in a single `try/except`.
- **`error_node`** — Terminal: writes a human-readable `final_text` and resets `normalized_request` to `{}`.

### Issues Found

- **[HIGH]** `extract_request_node` passes raw LLM output directly to `json.loads` without stripping markdown code fences (` ```json ... ``` `). If the model wraps its response in a code block — common with most hosted models — parsing fails and the entire request is discarded. A pre-parse strip/regex is needed.
- **[HIGH]** `prepare_ticket_node` has hardcoded Odoo team, type, category, and tag string literals (e.g. `"Presupuestos"`, `"Soporte cliente"`). If these values change in Odoo the node silently builds a payload that `create_ticket_node` will fail to resolve at runtime, only surfacing as a generic error string. These should come from config or the shared catalog.
- **[HIGH]** `BudgetState` uses `TypedDict` (strict, `total=True`) but `IntakeState` uses `TypedDict, total=False`. This inconsistency means `IntakeState` fields have no runtime enforcement; a missing `source_input` or `normalized_request` would raise a `KeyError` inside a node instead of a clear validation error at graph entry.
- **[MEDIUM]** `create_ticket_node` catches all exceptions with a bare `except Exception as e` and converts them to a string error. This hides the stack trace and makes debugging Odoo connectivity issues hard. Logging the exception before returning the error dict would help.
- **[MEDIUM]** `error_node` resets `normalized_request` to `{}`. If the error occurred before `extract_request_node` ran, `normalized_request` was never set; resetting it is harmless but misleading. If it ran and succeeded, overwriting it with `{}` destroys useful diagnostic context that callers might want to inspect.
- **[MEDIUM]** `prepare_input_node` returns `{"error": "...", }` (no `extracted_text` key) when validation fails. Because `IntakeState` is `total=False`, LangGraph will merge this partial dict without complaint, but `extracted_text` will be absent from state. Downstream nodes that read `state["extracted_text"]` directly (not via `.get()`) would raise `KeyError` if the routing logic ever allowed them to run.
- **[LOW]** No type annotations on `IntakeDependencies.llm` — typed as `object`. Should be `BaseChatModel` or the concrete type from `shared.llm`.
- **[LOW]** `prepare_ticket_node` truncates requirements to 5 items and missing-information notes to 3 in the ticket description, but there is no warning or log when truncation occurs.

---

## budget_agent

### Purpose
Receives a `normalized_request` dict (produced by `intake_agent`), maps requirements to product codes via the shared catalog, optionally enriches with per-client quote history, calls an MCP pricing service to compute line items, renders a natural-language quote with the LLM, and persists the quote to an in-memory store. Runs independently from `intake_agent`; expects `normalized_request` to already exist in state at invocation.

### State Schema
File: `agents/budget_agent/state.py` — `BudgetState(TypedDict)` (strict, `total=True`)

| Field | Type | Set by |
|---|---|---|
| `messages` | `Annotated[list, add_messages]` | All nodes |
| `normalized_request` | `dict` | Caller (initial input) |
| `selected_products` | `list[str]` | `prepare_budget_node` |
| `retrieved_memory` | `dict` | `retrieve_memory_node` |
| `customer_profile` | `dict` | `pricing_node` |
| `quote_result` | `dict` | `pricing_node` |
| `final_text` | `str` | `render_quote_node` or `error_node` |
| `error` | `str \| None` | Any node on failure |

- `total=True` (default) — all fields are required at type-check time. However, `normalized_request` is the only field set by the caller; the rest are written progressively by nodes, so mypy/pyright would flag the initial invocation unless the caller passes a full dict with all keys.

### Graph Topology
```
START
  └─► prepare_budget_node ──(error?)──► error_node ──► END
                           └──────────► retrieve_memory_node
                                               └──────────► pricing_node ──(error?)──► error_node ──► END
                                                                          └──────────► render_quote_node
                                                                                              └──────────► persist_memory_node ──► END
```
- Uses `InMemorySaver` checkpointer — state is checkpointed per `thread_id`, enabling multi-turn conversation context within the same process lifetime.
- No cycles.
- `retrieve_memory_node` never routes to `error_node` — memory absence is treated as a non-fatal soft event (returns empty/default `StoredQuoteMemory`).

### Key Nodes

- **`prepare_budget_node`** — Maps `requirements` list to product codes via `map_requirements_to_products`. Fails explicitly if requirements are empty or yield no products.
- **`retrieve_memory_node`** — Queries `QuoteMemoryStore` for the last quote tied to `company_name`. Always succeeds; missing history returns a default object. Sets `retrieved_memory`.
- **`pricing_node`** — Calls `MCPBudgetService.get_budget_context` (async). Builds `QuoteResult` (Pydantic model) and `QuoteLine` list from the MCP response. Increments `version` based on memory history. Serialises result with `.model_dump()` before storing in state (state holds plain dicts, not Pydantic objects).
- **`render_quote_node`** — Sends the full normalized request, customer profile, memory, and quote result as a large JSON-embedded prompt to the LLM. Returns the LLM's text as `final_text`. No structured output validation.
- **`persist_memory_node`** — Constructs a `StoredQuoteMemory` object and appends it via `QuoteMemoryStore.append_quote`. Uses `deps.memory_store.now_iso()` for the timestamp (avoids direct datetime import, but ties timestamp generation to the store instance).
- **`error_node`** — Terminal: writes human-readable `final_text`. Does not reset any data fields (unlike `intake_agent`'s `error_node`).

### Issues Found

- **[CRITICAL]** `BudgetState` is `total=True` but the caller only provides `normalized_request` at invocation time. At runtime, LangGraph merges partial state, so this works, but static type checkers will report errors for every field not provided in the initial state dict. More importantly, `render_quote_node` accesses `state["customer_profile"]`, `state["quote_result"]`, and `state["retrieved_memory"]` with direct key access (not `.get()`). If `pricing_node` ever routes to `error_node` due to an MCP failure, these keys would be absent, and `render_quote_node` would raise `KeyError` — but the routing logic (`_route_after_pricing`) correctly prevents `render_quote_node` from running after an error. This is safe today but fragile; any future graph topology change could break it silently.
- **[HIGH]** `InMemorySaver` is instantiated inside `build_budget_graph()`. Every call to `build_budget_graph()` creates a fresh checkpointer, losing all previous checkpoint history. For persistent multi-turn sessions, the checkpointer must be instantiated externally and passed in, or a database-backed checkpointer must be used.
- **[HIGH]** `render_quote_node` embeds the full `normalized_request`, `customer_profile`, `retrieved_memory`, and `quote_result` as JSON in the prompt with no size guard. For large catalogs or verbose MCP responses this can exceed the model's context window silently, causing a truncated or refused response with no error surfaced to the graph.
- **[HIGH]** `pricing_node` manually recalculates `line_total = unit_price * quantity` from the MCP response rather than trusting the MCP's own `line_total`. If the MCP applies per-line discounts or rounding, the recalculated value will differ from the official total, creating a subtotal/line-items mismatch in `QuoteResult`.
- **[MEDIUM]** `QuoteMemoryStore` is in-memory (`QuoteMemoryStore()`). On process restart all quote history is lost. The `InMemorySaver` checkpointer and this store are both RAM-only, meaning no real persistence across sessions despite being labelled as a "memory" system.
- **[MEDIUM]** `retrieve_memory_node` does not inject a `config` parameter into its signature yet calls `_get_deps(config)` — wait, it does accept `config`. However the return value always succeeds even if the store raises. Any exception inside `deps.memory_store.get_last_quote_memory` would propagate uncaught and crash the graph without setting `error`.
- **[MEDIUM]** `persist_memory_node` returns only a `messages` update with no explicit `error: None`. If `append_quote` raises, the exception is not caught, crashing the graph outside the normal error-routing pattern.
- **[LOW]** `BudgetDependencies.llm` is typed as `object`, same as in `IntakeDependencies`. Should be the concrete or protocol type.
- **[LOW]** `pricing_node` builds `QuoteResult` using `raw_quote.get("subtotal", 0)` and `raw_quote.get("total", 0)`. If the MCP returns these as strings (e.g. `"1500.00"`), the `float()` cast will succeed, but no validation is done against the sum of line totals. A mismatch would go undetected.

---

## Cross-cutting observations

- **Shared state contract between agents** — `budget_agent` consumes `normalized_request` produced by `intake_agent`, but there is no shared schema or Pydantic model enforcing this contract. Both agents use untyped `dict`. A breaking change in `extract_request_node`'s output structure would silently corrupt `budget_agent` without any import-time or test-time signal.
- **No tests for node functions** — Node functions are async and take `(state, config)` arguments, making them straightforward to unit-test with `pytest-asyncio`. No test files exist for either agent at review time.
- **Inconsistent `total=False` vs `total=True` on TypedDicts** — `IntakeState` uses `total=False`; `BudgetState` uses `total=True`. This asymmetry is confusing and should be aligned. The recommended pattern for LangGraph states is `total=False` with explicit defaults where needed.
- **No logging** — Neither agent uses Python's `logging` module. All diagnostic output is embedded in `AIMessage.content` strings visible only in the graph's message history. This makes production debugging very difficult. A structured logger should be added to every node.
- **`llm: object` type** — Both `IntakeDependencies` and `BudgetDependencies` declare `llm: object`. Replace with `BaseChatModel` (from `langchain_core.language_models`) to catch misconfiguration early.
- **Error state asymmetry** — `intake_agent`'s `error_node` clears `normalized_request`; `budget_agent`'s does not. Callers inspecting the post-run state need to handle these two different shapes.
- **No retry logic** — LLM calls and Odoo/MCP calls have no retry or exponential back-off. Transient network failures route to `error_node` permanently.
- **Hardcoded Spanish prompt strings** — Both LLM prompts are hardcoded in Spanish inside the node functions. Externalising prompts (to a prompts module or config file) would simplify A/B testing and localisation.
