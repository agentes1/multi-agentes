# PROJECT_CONTEXT — multi-agentes

> Auto-generated context document. Load at session start for full codebase awareness.

---

## 1. Project Summary

Python multi-agent system that converts inbound client messages (email / chat) into structured ERP sales quotes.
Two LangGraph agents run in sequence: `intake_agent` normalizes the raw input; `budget_agent` calls an MCP pricing server and writes a final quote text.
The system also creates helpdesk tickets in Odoo (OCA `helpdesk_mgmt`) via XML-RPC.
Primary users: internal pre-sales team; intended to automate quote generation for an Odoo ERP consultancy.

---

## 2. Tech Stack

| Component | Technology | Version / Notes |
|---|---|---|
| Language | Python | 3.11+ |
| Agent framework | LangGraph | latest (from `langgraph`) |
| LLM client | LangChain Ollama | `langchain-ollama` + `langchain-core` |
| Default LLM | Ollama local | `qwen3:4b`, temp=0; overrideable via env |
| API server | FastAPI + Uvicorn | latest |
| Data validation | Pydantic v2 | latest |
| MCP server | FastMCP | latest (`fastmcp`) |
| MCP client | LangChain MCP Adapters | `langchain_mcp_adapters` |
| Odoo integration | XML-RPC | `odoo_integration/odoo_api_wrapper.py` |
| Evaluation | DeepEval | 3.9.5 (pinned) |
| Linter / formatter | Ruff | configured in `pyproject.toml` |
| Type checker | Mypy | Python 3.11, strict mode |
| Test runner | pytest | asyncio_mode=auto |
| Memory persistence | JSON file | `memory_data/quote_memory.json` |

---

## 3. Folder Structure

```
multi-agentes/
├── api.py                  # FastAPI app; single entry point
├── pipeline.py             # Orchestrator: runs intake_agent then budget_agent
├── pyproject.toml          # Ruff + Mypy + pytest config
├── requirements.in         # Top-level deps (pip-compile source)
├── requirements.txt        # Locked deps
│
├── agents/
│   ├── intake_agent/       # Agent 1: normalizes raw input, creates Odoo ticket
│   └── budget_agent/       # Agent 2: maps products, calls MCP, renders quote text
│
├── schemas/
│   ├── common.py           # UrgencyLevel Literal type
│   └── budget.py           # NormalizedRequest, QuoteResult, QuoteLine, StoredQuoteMemory, RetrievedQuoteMemory
│
├── shared/
│   ├── config.py           # All constants and path definitions
│   ├── llm.py              # get_llm() factory (ChatOllama)
│   ├── catalog.py          # Product catalog, synonym map, normalize_requirement()
│   ├── memory_store.py     # QuoteMemoryStore (JSON file persistence)
│   └── deepeval_eval.py    # DeepEval metric helpers for evals
│
├── mcp/
│   └── mcp_servidor_precios.py   # Simulated MCP pricing server (FastMCP)
│
├── services/
│   └── mcp_budget.py       # MCPBudgetService: client wrapper for MCP server
│
├── odoo_integration/
│   ├── odoo_api_wrapper.py # OdooAPIWrapper: XML-RPC CRUD for helpdesk.ticket
│   └── odoo_mcp_server.py  # Alternative MCP server backed by real Odoo
│
├── odoo/
│   └── addons/             # OCA helpdesk_mgmt + extensions (source only, not deployed here)
│
├── evals/
│   ├── models.yaml         # List of Ollama models for benchmark
│   ├── benchmark_cases.jsonl  # Input test cases for multi-model eval
│   ├── run_multi_model_eval.py # CLI benchmark runner
│   ├── reporting.py        # Metrics computation and Markdown report generator
│   └── reports/            # Output: JSON + Markdown per run
│
├── tests/                  # pytest: intake, budget, API, deepeval unit tests
├── memory_data/            # Runtime: quote_memory.json (git-ignored)
├── pruebas/                # POC experiments: CrewAI, LangGraph, LangChain, Google ADK
├── scripts/                # Setup helpers (Odoo data seeding, etc.)
└── docs/                   # Guides, diagrams, this file
```

---

## 4. Architecture & Data Flow

```
Client (email / chat JSON)
        |
        v
POST /process  (api.py)
        |
        v
run_pipeline()  (pipeline.py)
        |
        |--- Step 1: build_intake_graph().ainvoke({source_input})
        |        |
        |        |  IntakeDependencies: ChatOllama + OdooAPIWrapper
        |        |
        |        +--> prepare_input_node      (normalize channel → extracted_text)
        |        +--> extract_request_node    (LLM call → NormalizedRequest dict + ticket_type)
        |        +--> prepare_ticket_node     (map ticket_type → Odoo team/type/category/tags)
        |        +--> create_ticket_node      (XML-RPC → helpdesk.ticket ID)
        |        +--> error_node              (if any step sets state["error"])
        |
        |  Returns: {normalized_request, error}
        |
        |--- Step 2: build_budget_graph().ainvoke({normalized_request})
        |        |
        |        |  BudgetDependencies: ChatOllama + QuoteMemoryStore + MCPBudgetService
        |        |
        |        +--> prepare_budget_node     (map requirements → product codes via catalog)
        |        +--> retrieve_memory_node    (load last quote from JSON file)
        |        +--> pricing_node            (MCP stdio: get_customer_profile + calculate_quote)
        |        +--> render_quote_node       (LLM call → final_text in Spanish)
        |        +--> persist_memory_node     (append StoredQuoteMemory to JSON file)
        |        +--> error_node              (if prepare or pricing sets state["error"])
        |
        |  Returns: {quote_result, final_text, error}
        |
        v
ProcessResponse {ok, thread_id, normalized_request, quote_result, final_text}
        |
        v
HTTP 200 (ok=true) or HTTP 400 (ok=false, detail contains error)
```

**MCP communication:** `MCPBudgetService` launches `mcp_servidor_precios.py` as a subprocess via `stdio` transport using the same Python interpreter. Tools called: `get_customer_profile`, `calculate_quote`.

**Odoo ticket creation:** `OdooAPIWrapper` resolves team/type/category/tag names to IDs via XML-RPC `search_read`, then calls `create` on `helpdesk.ticket`.

---

## 5. Agents

### intake_agent

**Purpose:** Parse raw channel input (email/chat) into a structured `NormalizedRequest` and create a helpdesk ticket in Odoo.

**Dependencies (`IntakeDependencies`):**

| Field | Type | Provided by |
|---|---|---|
| `llm` | `ChatOllama` | `get_llm(model)` |
| `odoo_service` | `OdooAPIWrapper` | `build_dependencies()` |

**State (`IntakeState` — TypedDict, total=False):**

| Field | Type | Description |
|---|---|---|
| `messages` | `list` (append) | LangGraph message log |
| `source_input` | `dict` | Raw channel payload |
| `extracted_text` | `str` | Unified text from channel |
| `normalized_request` | `dict` | LLM-structured request (NormalizedRequest shape) |
| `ticket_type` | `str` | `budget` / `issue` / `discard` |
| `ticket_payload` | `dict` | Odoo-ready ticket fields |
| `ticket_id` | `int` | Created helpdesk.ticket ID |
| `final_text` | `str` | Human-readable outcome |
| `error` | `str \| None` | Error message; None = success |

**Graph nodes:**

| Node | What it does |
|---|---|
| `prepare_input_node` | Extracts `extracted_text` from email/chat fields; fails if empty |
| `extract_request_node` | **LLM call** — structured JSON extraction (company, requirements, urgency, ticket_type, missing_information); normalizes requirements via `shared/catalog.py` |
| `prepare_ticket_node` | Maps ticket_type → `team_name`, `type_name`, `category_name`, `tag_names`, `priority`; builds `ticket_payload` |
| `create_ticket_node` | Resolves names → IDs via `OdooAPIWrapper`; calls `create_helpdesk_ticket()` |
| `error_node` | Terminal error handler; sets `final_text = "Error: ..."` |

**LLM prompt in `extract_request_node`:** Extracts structured JSON with fields: `company_name`, `project_summary`, `requirements` (constrained list), `urgency`, `ticket_type`, `missing_information`. Validates required keys, normalizes urgency/ticket_type values.

---

### budget_agent

**Purpose:** Convert `NormalizedRequest` into a calculated `QuoteResult` and write a professional Spanish quote text.

**Dependencies (`BudgetDependencies`):**

| Field | Type | Provided by |
|---|---|---|
| `llm` | `ChatOllama` | `get_llm(model)` |
| `memory_store` | `QuoteMemoryStore` | `QuoteMemoryStore()` |
| `mcp_service` | `MCPBudgetService` | `MCPBudgetService()` |

**State (`BudgetState` — TypedDict):**

| Field | Type | Description |
|---|---|---|
| `messages` | `list` (append) | LangGraph message log |
| `normalized_request` | `dict` | From intake_agent output |
| `selected_products` | `list[str]` | Product codes from catalog mapping |
| `retrieved_memory` | `dict` | Last quote data for company |
| `customer_profile` | `dict` | Segment + discount from MCP |
| `quote_result` | `dict` | Serialized `QuoteResult` |
| `final_text` | `str` | LLM-rendered quote text |
| `error` | `str \| None` | Error message; None = success |

**Graph nodes:**

| Node | What it does |
|---|---|
| `prepare_budget_node` | Calls `map_requirements_to_products()`; fails if no mappable products |
| `retrieve_memory_node` | Calls `QuoteMemoryStore.get_last_quote_memory(company_name)` |
| `pricing_node` | Calls `MCPBudgetService.get_budget_context()` → builds `QuoteResult`; sets version and `based_on_previous_quote` from memory |
| `render_quote_node` | **LLM call** — renders professional Spanish quote from structured data |
| `persist_memory_node` | Calls `QuoteMemoryStore.append_quote(StoredQuoteMemory)` |
| `error_node` | Terminal error handler |

**LLM prompt in `render_quote_node`:** Passes `normalized_request`, `customer_profile`, `retrieved_memory`, `quote_result` as JSON. Requests output with: title, project summary, modules, subtotal, discount, total, preliminary note, and optional historical reference. Explicitly forbidden to invent amounts.

**Checkpointer:** `InMemorySaver` (RAM-only, resets on restart). `thread_id` from pipeline call is required.

---

## 6. Shared Infrastructure

### `shared/config.py`

**Purpose:** Single source of all runtime constants and paths.

Key exports:
- `PROJECT_ROOT` — `Path` to repo root
- `MCP_SERVER_PATH` — `PROJECT_ROOT / "mcp" / "mcp_servidor_precios.py"`
- `MEMORY_FILE_PATH` — `PROJECT_ROOT / "memory_data" / "quote_memory.json"`
- `OLLAMA_MODEL` — default `"qwen3:4b"`
- `OLLAMA_TEMPERATURE` — default `0`
- `ODOO_BASE_URL` — `"http://localhost:8069/xmlrpc/2"`
- `ODOO_DB`, `ODOO_USERNAME`, `ODOO_PASSWORD`

Env vars checked at runtime:
- `OLLAMA_MODEL_OVERRIDE` — overrides `OLLAMA_MODEL`
- `OLLAMA_TEMPERATURE_OVERRIDE` — overrides `OLLAMA_TEMPERATURE`

---

### `shared/llm.py`

**Purpose:** Factory for `ChatOllama` instances with override support.

Key exports:
- `get_llm(model=None, temperature=None) -> ChatOllama`

Env vars:
- `OLLAMA_MODEL_OVERRIDE`
- `OLLAMA_TEMPERATURE_OVERRIDE`

---

### `shared/catalog.py`

**Purpose:** Static product catalog mapping with synonym normalization.

Key exports:
- `REQUIREMENT_TO_PRODUCT: dict` — e.g. `"crm" → "crm_base"`, `"presupuestos" → "quotation_ai"`
- `REQUIREMENT_SYNONYMS: dict` — e.g. `"erp" → "odoo"`, `"cotizaciones" → "presupuestos"`
- `normalize_requirement(requirement: str) -> str`
- `map_requirements_to_products(requirements: list[str]) -> list[str]`

Product codes: `crm_base`, `email_ai`, `quotation_ai`, `odoo_connector`, `dashboard`

---

### `shared/memory_store.py`

**Purpose:** JSON file-backed persistent store for quote history per company.

Key exports:
- `QuoteMemoryStore` class
  - `get_company_history(company_name) -> list[dict]`
  - `get_last_quote_memory(company_name) -> RetrievedQuoteMemory`
  - `append_quote(item: StoredQuoteMemory) -> None`
  - `now_iso() -> str` (static, UTC ISO format)

Env vars: none (path from `shared/config.py`).

---

### `shared/deepeval_eval.py`

**Purpose:** DeepEval metric helpers for pipeline evaluation.

Key exports:
- `get_eval_model(model_name="qwen3:4b") -> OllamaModel`
- `get_eval_metrics(model_name="qwen3:4b") -> list` — returns `[AnswerRelevancyMetric, GEval]`
- `build_pipeline_test_case(source_input, pipeline_result) -> LLMTestCase`

---

## 7. API Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| `POST` | `/process` | Run full pipeline; returns quote or 400 error | None |
| `GET` | `/health` | Liveness check; returns `{"status": "ok"}` | None |
| `GET` | `/docs` | FastAPI Swagger UI (auto-generated) | None |

**Request body for `POST /process`:**
```json
{
  "source_input": {
    "channel": "email",
    "from": "client@company.com",
    "subject": "...",
    "body": "..."
  },
  "thread_id": "optional-string"
}
```

**Response body `ProcessResponse`:**

| Field | Type | Notes |
|---|---|---|
| `ok` | `bool` | `true` = success |
| `thread_id` | `str \| None` | Echo of input |
| `stage` | `str \| None` | Which agent failed (if `ok=false`) |
| `error` | `str \| None` | Error message |
| `validation_notes` | `list[str]` | Non-blocking warnings from intake |
| `normalized_request` | `dict` | `NormalizedRequest` fields |
| `quote_result` | `dict` | `QuoteResult` fields |
| `final_text` | `str` | LLM-rendered quote |

On error: HTTP 400, body = full `ProcessResponse` dict in `detail`.

---

## 8. MCP Tools

**Server file:** `mcp/mcp_servidor_precios.py`
**Server name:** `odoo_precios_simulados`
**Transport:** `stdio` (launched as subprocess by `MCPBudgetService`)

| Tool | Description | Input fields |
|---|---|---|
| `list_catalog` | Returns full `CATALOGO` dict | none |
| `get_product` | Returns single product detail | `product_code: str` |
| `get_customer_profile` | Returns client segment + discount | `company_name: str` |
| `calculate_quote` | Calculates subtotal, discount, total, lines | `product_codes: list[str]`, `company_name: str` |

**Hardcoded catalog prices:**

| Code | Name | Price (EUR) |
|---|---|---|
| `crm_base` | CRM Base | 1,200 |
| `email_ai` | Clasificación de emails con IA | 1,800 |
| `quotation_ai` | Generación de presupuestos con IA | 2,200 |
| `odoo_connector` | Conector con Odoo | 1,500 |
| `dashboard` | Dashboard comercial | 900 |

**Hardcoded client discounts:** `ACME` → 10% (pyme), `MEGACORP` → 15% (enterprise). All others → 0%.

**Client wrapper:** `services/mcp_budget.py` — `MCPBudgetService.get_budget_context(company_name, product_codes) -> dict`. Uses `MultiServerMCPClient` + `load_mcp_tools`. Result parsing via `_parse_mcp_result()` handles dict or `[{"text": "..."}]` shapes.

---

## 9. Eval System

### Multi-model benchmark

**Run command:**
```bash
python -m evals.run_multi_model_eval \
  --cases evals/benchmark_cases.jsonl \
  --out-dir evals/reports
# or with explicit models:
python -m evals.run_multi_model_eval --models qwen3:4b llama3.2 mistral
```

**Models configured in `evals/models.yaml` (active):**

| Model | Size | Notes |
|---|---|---|
| `mistral` | 4.4 GB | Strong reasoning |
| `llama3.2` | 2.0 GB | Lightweight (Meta 3.2 3B) |
| `qwen3:4b` | 2.5 GB | Default model for project |
| `gemma3:4b` | 3.3 GB | Google |

Many others commented out (mistral-nemo, llama3.1, llama3.3, qwen2.5, qwen3:8b, phi4, phi4-mini, gemma3:12b).

**Benchmark cases:** `evals/benchmark_cases.jsonl` — JSONL, each line has `case_id`, `source_input`, optional `thread_id`, `tags`.

**Metrics:**

| Metric | Implementation | Scale | Threshold | Scope |
|---|---|---|---|---|
| `answer_relevancy_score` | `deepeval.AnswerRelevancyMetric` | 0.0–1.0 | ≥ 0.5 | `ok=true` cases only |
| `geval_score` | `deepeval.GEval` ("Quote Quality") | 0.0–1.0 | ≥ 0.5 | `ok=true` cases only |
| `success_rate` | `compute_rate(rows, "ok")` | 0–100% | — | all cases |
| `latency_p50_ms` | `compute_latency_percentiles(..., (50, 95))` | ms | — | all cases |
| `latency_p95_ms` | same | ms | — | all cases |

**Winner selection (`select_winner`):** priority order: success_rate DESC → answer_relevancy_mean DESC → geval_mean DESC → latency_p50 ASC → model name ASC.

**Outputs:** Two files per run in `evals/reports/`:
- `multi_model_eval_{run_id}.json` — full raw results + summaries
- `multi_model_eval_{run_id}.md` — Markdown table + winner

**Reporting helpers (`evals/reporting.py`):**
- `compute_rate(rows, key)` → float
- `compute_mean(rows, key)` → float
- `compute_latency_percentiles(rows, percentiles)` → dict
- `group_errors(rows)` → dict[str, int]
- `summarize_model(rows)` → aggregated dict
- `select_winner(model_summaries)` → str
- `render_markdown_report(run_id, model_summaries, winner)` → str

---

## 10. How to Run (dev setup)

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com) running locally with at least one model
- (Optional) Odoo 18 at `http://localhost:8069` with OCA `helpdesk_mgmt` installed

### Steps

```bash
# 1. Clone and enter project
git clone https://github.com/agentes1/multi-agentes.git
cd multi-agentes

# 2. Create virtual environment
python -m venv .venv

# 3. Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# Activate (bash/macOS/Linux)
source .venv/bin/activate

# 4. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 5. Pull default Ollama model
ollama pull qwen3:4b

# 6. (Optional) Set model override via env
export OLLAMA_MODEL_OVERRIDE=llama3.2
export OLLAMA_TEMPERATURE_OVERRIDE=0

# 7. Start API server
python api.py
# Runs on http://localhost:8000 with reload=True

# 8. Verify
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# 9. Test full pipeline
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"source_input":{"channel":"email","from":"x@acme.com","subject":"Presupuesto ERP","body":"Necesitamos CRM y facturación."}}'
```

### Run tests
```bash
# Unit + integration tests
python -m pytest tests -q

# DeepEval contract test only
python -m pytest tests/test_deepeval_eval.py -q
```

### Run multi-model benchmark
```bash
python -m evals.run_multi_model_eval \
  --cases evals/benchmark_cases.jsonl \
  --out-dir evals/reports
```

### Key env vars

| Variable | Default | Effect |
|---|---|---|
| `OLLAMA_MODEL_OVERRIDE` | `qwen3:4b` | Override LLM model for all agents |
| `OLLAMA_TEMPERATURE_OVERRIDE` | `0` | Override LLM temperature |

Odoo credentials are hardcoded in `shared/config.py` (not env-based — see Known Issues).

---

## 11. Known Issues / TODOs

- **Odoo credentials hardcoded** in `shared/config.py` (`ODOO_BASE_URL`, `ODOO_DB`, `ODOO_USERNAME`, `ODOO_PASSWORD`). Should be moved to env vars or a `.env` file.
- **MCP pricing server is simulated** — `mcp/mcp_servidor_precios.py` uses hardcoded `CATALOGO` and `CLIENTES` dicts. Real Odoo pricing not yet wired.
- **Only two clients have discounts** in the MCP server (`ACME`, `MEGACORP`). All others get 0% discount.
- **`InMemorySaver` checkpointer** in `budget_agent` resets on each server restart — no persistent conversation state.
- **`memory_data/quote_memory.py`** — error handling in `_load_all()` silently returns `{}` on any exception (comment in code: "modificar más adelante para mayor especifidad").
- **No authentication** on API endpoints — `allow_origins=["*"]` CORS and no API key.
- **`intake_agent` creates Odoo tickets for ALL inputs** including `discard` ticket type (routed to "Soporte cliente / Interno" team) — no skip path.
- **`render_quote_node` comment** in `budget_agent/nodes.py`: "→ más adelante sustituir por formato de presupuesto Odoo" — LLM-rendered text is the current final output, not a native Odoo quote.
- **`odoo_integration/odoo_mcp_server.py`** exists as an alternative MCP server backed by real Odoo but is not connected to the main pipeline.
- **No HITL (human-in-the-loop)** — the pipeline runs end-to-end with no approval step. Planned per `project_vision.md`.
- **No semantic router** — ticket classification is done entirely by the LLM in `extract_request_node`. Misclassification silently falls back to `discard`.
- **Test coverage gaps** — eval tests depend on Ollama being available locally; CI will fail without it.
- **`pruebas/` directory** contains POC experiments (CrewAI, LangGraph POC, LangChain Structured, Google ADK) — not connected to production code.
