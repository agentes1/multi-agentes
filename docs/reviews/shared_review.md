# Shared Infrastructure Review

> Reviewed: 2026-04-14
> Scope: `shared/` and `schemas/` modules that form the foundation of the multi-agentes pipeline.
> Intended audience: AI agents starting cold sessions and developers onboarding to the project.

---

## shared/config.py

### Purpose
Central place for project-wide constants. Acts as the single source of truth for file paths, model settings, and Odoo connection parameters. No classes — pure module-level assignments.

### Key exports
- `PROJECT_ROOT` — absolute path derived from the file's own location
- `MCP_SERVER_PATH` — path to the MCP pricing server script
- `MEMORY_FILE_PATH` — path to the persistent quote memory JSON file
- `OLLAMA_MODEL` — default LLM model name (`"qwen3:4b"`)
- `OLLAMA_TEMPERATURE` — default temperature (`0`)
- `ODOO_BASE_URL`, `ODOO_DB`, `ODOO_USERNAME`, `ODOO_PASSWORD` — Odoo XML-RPC connection params

### Config / Env vars
- None. All values are hardcoded literals. No `os.getenv` calls, no `.env` loading.

### Issues
- **CRITICAL** — `ODOO_PASSWORD = 'adminpass'` is a hardcoded credential committed to source. This violates basic secret-management hygiene. Rotate on any non-local deployment; move to environment variables or a secrets manager (`python-dotenv` + `.env` + `.gitignore`, or an external vault).
- **CRITICAL** — `ODOO_USERNAME = 'admin'` and `ODOO_DB = 'odoo'` are also hardcoded. While not passwords, exposing the username and database name in source tightens the attack surface if the repo is shared.
- **HIGH** — No environment variable overrides for any Odoo setting. `shared/llm.py` already demonstrates the pattern (`os.getenv("OLLAMA_MODEL_OVERRIDE")`); the same should be applied to every secret/URL here.
- **MEDIUM** — `ODOO_BASE_URL` targets `localhost:8069`, which silently breaks in any non-local environment (CI, staging, Docker) with no warning. Document clearly or guard with a startup check.
- **LOW** — No type annotations on module-level constants. Adding `Final[str]` / `Final[Path]` (`typing`) makes intent explicit and enables static analysis.

---

## shared/llm.py

### Purpose
Factory function that returns a configured `ChatOllama` instance. Provides a single integration point for all agents that need an LLM, allowing model and temperature to be overridden without editing `config.py`.

### Key exports
- `get_llm(model, temperature) -> ChatOllama` — creates and returns a `ChatOllama` object

### Config / Env vars
- `OLLAMA_MODEL_OVERRIDE` (optional) — overrides the default model name from `config.py`
- `OLLAMA_TEMPERATURE_OVERRIDE` (optional) — overrides the default temperature; parsed with `int()`

### Issues
- **HIGH** — Temperature is cast with `int()` but LLM temperatures are typically floats (e.g., `0.7`). Using `int()` silently truncates a float value supplied via the env var. Change to `float()`.
- **MEDIUM** — `int(os.getenv("OLLAMA_TEMPERATURE_OVERRIDE", str(OLLAMA_TEMPERATURE)))` will raise `ValueError` if the env var is set to a non-numeric string. Wrap in a `try/except` or use `float(os.getenv(...) or OLLAMA_TEMPERATURE)`.
- **MEDIUM** — There is no base URL configuration for the Ollama server (default is `http://localhost:11434`). In Docker or CI environments the Ollama server may be on a different host. Add an `OLLAMA_BASE_URL` env var override.
- **LOW** — Return type annotation `ChatOllama` couples callers to the concrete Ollama implementation. Consider returning `BaseChatModel` (LangChain interface) to allow future provider swaps without changing call sites.

---

## shared/catalog.py

### Purpose
Static lookup tables and helper functions that map free-text user requirements to internal product codes. Pure functions with no I/O or side effects.

### Key exports
- `REQUIREMENT_TO_PRODUCT: dict[str, str]` — canonical requirement name → product code
- `REQUIREMENT_SYNONYMS: dict[str, str]` — synonym → canonical requirement name
- `normalize_requirement(requirement: str) -> str` — lowercases, strips, and resolves synonyms
- `map_requirements_to_products(requirements: list[str]) -> list[str]` — maps a list of requirement strings to deduplicated product codes

### Config / Env vars
- None.

### Issues
- **HIGH** — Unmapped requirements are silently dropped. `map_requirements_to_products` skips any requirement not found in `REQUIREMENT_TO_PRODUCT` without logging or returning a warning. Callers have no visibility into which user-stated needs were ignored. Add a separate list of unrecognised requirements to the return value, or at minimum log a warning.
- **MEDIUM** — The synonym dictionary only handles exact lowercased strings. Multi-word synonyms with extra whitespace (e.g., `"automatizacion  comercial"`) will miss; `normalize_requirement` already strips but does not collapse inner whitespace. Add `re.sub(r'\s+', ' ', value)` before the lookup.
- **MEDIUM** — The catalog is entirely hardcoded. Adding a product requires editing source code and redeploying. Consider loading from a JSON/YAML config file that can be updated without code changes.
- **LOW** — `normalize_requirement` accepts `requirement: str` but immediately calls `str(requirement)`, implying it anticipates non-string input. Either enforce `str` at the type boundary or accept `Any` explicitly.
- **LOW** — `map_requirements_to_products` uses a manual deduplication guard (`if code not in products`). Replace with an `OrderedDict` or use `dict.fromkeys()` to preserve order while deduplicating — it is cleaner and O(1) per lookup.

---

## shared/memory_store.py

### Purpose
Persistent JSON-file-backed store for quote history, keyed by company name. Each company has a list of `StoredQuoteMemory` entries. Provides read and append operations; there is no update or delete.

### Key exports
- `QuoteMemoryStore` class:
  - `__init__(file_path?)` — sets up the file path, creates the parent directory and an empty JSON file if needed
  - `get_company_history(company_name) -> list[dict]` — returns all stored quotes for a company
  - `get_last_quote_memory(company_name) -> RetrievedQuoteMemory` — returns a structured summary of the most recent quote
  - `append_quote(item: StoredQuoteMemory) -> None` — appends a new quote to the company's history and persists to disk
  - `now_iso() -> str` (static) — returns the current UTC time in ISO 8601 format

### Config / Env vars
- `MEMORY_FILE_PATH` from `shared/config.py` (used as default when no `file_path` is passed to `__init__`).

### Issues
- **CRITICAL** — No file locking. `_load_all` reads the file and `_save_all` writes it back in two separate operations. If two agent processes call `append_quote` concurrently (which is plausible in a multi-agent setup), one write will overwrite the other and data will be silently lost. Use `filelock` or `fcntl` to acquire an exclusive lock around the load–modify–save cycle.
- **HIGH** — `_load_all` silently swallows all exceptions (`except Exception: return {}`). A corrupt JSON file (e.g., partial write from a crash) returns an empty dict, causing history to be silently wiped the next time `append_quote` runs. Catch `json.JSONDecodeError` specifically; for other errors re-raise or log and raise.
- **HIGH** — There is no size or age limit on the per-company history list. A long-running deployment will accumulate unbounded history, growing the JSON file indefinitely. Add a configurable cap (e.g., keep last N entries) or periodic archival.
- **MEDIUM** — `get_last_quote_memory` reads the last element of the history list (`history[-1]`), which is only correct if entries are always appended in chronological order. This is currently true, but there is no timestamp-based sort as a safety net. If the file is ever manually edited out of order, the "last" quote will be wrong.
- **MEDIUM** — `now_iso()` is a static method on `QuoteMemoryStore` but is unrelated to the store's state. It would be better placed as a module-level utility function, or callers should generate the timestamp and pass it in, keeping the store's API to pure persistence.
- **LOW** — The whole JSON file is loaded and re-serialised on every read and write, even for a single company's entry. For a small dataset this is fine, but it will not scale. Document this limitation in a comment so future contributors know to replace the backend if volume grows.

---

## shared/deepeval_eval.py

### Purpose
Evaluation helpers that wrap the `deepeval` library for measuring pipeline output quality. Defines two metrics (answer relevancy and quote quality) and a function to construct `LLMTestCase` objects from pipeline I/O.

### Key exports
- `get_eval_model(model_name) -> OllamaModel` — returns a DeepEval-compatible Ollama evaluator model
- `get_eval_metrics(model_name) -> list` — returns `[AnswerRelevancyMetric, GEval("Quote Quality")]`
- `build_pipeline_test_case(source_input, pipeline_result) -> LLMTestCase` — converts raw pipeline dicts into a `LLMTestCase` with a human-readable input string

### Config / Env vars
- Default model name `"qwen3:4b"` is hardcoded in both `get_eval_model` and `get_eval_metrics`. Neither reads from `shared/config.py` (`OLLAMA_MODEL`), creating a potential consistency gap if the main model is changed.

### Issues
- **HIGH** — The default `model_name` in `get_eval_model` and `get_eval_metrics` is `"qwen3:4b"` hardcoded, duplicating the value already defined in `shared/config.py`. These two should import and use `OLLAMA_MODEL` from `config.py` to avoid drift when the model is changed in one place but not the other.
- **HIGH** — `get_eval_metrics` return type is `list` (untyped). Should be `list[AnswerRelevancyMetric | GEval]` or at least `list[Any]` with a comment. Untyped lists make static analysis blind to the contents.
- **MEDIUM** — Both thresholds are set to `0.5` with no explanation or configuration point. These are evaluation quality gates; they should either be named constants or be configurable via env vars so they can be tuned per environment without code changes.
- **MEDIUM** — `build_pipeline_test_case` only handles `"email"` and `"chat"` channels explicitly; all others fall back to `json.dumps`. If a new channel type is added (e.g., `"api"`, `"form"`), it silently gets raw JSON as the input string, which may degrade metric quality. Add a comment warning about this, or raise/log for unknown channels.
- **LOW** — `build_pipeline_test_case` uses `dict[str, Any]` for both arguments. Using the actual Pydantic models (`NormalizedRequest`, `QuoteResult`) as parameter types would provide validation and IDE support. At minimum, document the expected keys in the docstring.
- **LOW** — When `pipeline_result.get("ok")` is `False`, `actual_output` is set to the error string. Feeding an error message as the "actual output" into `AnswerRelevancyMetric` will produce a meaningless score. Failed cases should be excluded from metric evaluation or flagged separately.

---

## schemas/common.py

### Purpose
Defines shared type aliases used across the schema layer. Currently contains only one export.

### Key exports
- `UrgencyLevel = Literal["baja", "media", "alta"]` — a string literal type for urgency values

### Config / Env vars
- None.

### Issues
- **LOW** — The file has no docstring. Given its role as the common schema foundation, a brief module docstring explaining the domain vocabulary (Spanish urgency levels: low/medium/high) would help agents and developers unfamiliar with Spanish.
- **LOW** — `UrgencyLevel` is a `Literal` type alias, not a proper `Enum`. Using `enum.Enum` (or `StrEnum` in Python 3.11+) would allow iteration, comparison helpers, and serialisation via Pydantic with `use_enum_values=True`. The current approach is functional but less robust.

---

## schemas/budget.py

### Purpose
Pydantic data models for the quoting pipeline. Defines the shapes of data flowing between agents: normalised customer requests, quote line items, full quote results, and memory structures for persistence and retrieval.

### Key exports
- `NormalizedRequest` — parsed representation of a customer inquiry (company, summary, requirements list, urgency, missing info)
- `QuoteLine` — a single line item in a quote (product code, description, price, quantity, line total)
- `QuoteResult` — a complete quote document (company, lines, financial totals, currency, warnings, metadata)
- `RetrievedQuoteMemory` — summary of the last quote retrieved from memory for a given company
- `StoredQuoteMemory` — full record persisted to the JSON memory store (request, products, result, text, timestamp)

### Config / Env vars
- None.

### Issues
- **HIGH** — `QuoteLine.line_total` is a plain `float` field with no validator enforcing that it equals `unit_price * quantity`. Nothing prevents a caller from storing `line_total=0.0` while `unit_price=500.0, quantity=2`. Add a `@model_validator(mode="after")` or a `@field_validator` that recomputes `line_total`, or make it a computed property.
- **HIGH** — `QuoteResult.subtotal`, `discount`, and `total` have no cross-field validation. `total` should equal `subtotal - discount`, but this is not enforced. A model validator should verify the relationship at construction time.
- **HIGH** — `StoredQuoteMemory.normalized_request`, `quote_result` are typed as plain `dict` instead of `NormalizedRequest` and `QuoteResult`. This bypasses Pydantic validation for the most critical data. Using the concrete models and calling `.model_dump()` only at serialisation time would catch schema drift early.
- **MEDIUM** — `QuoteResult.currency` defaults to `"EUR"` as a free-text string with no validation. If the pipeline ever handles other currencies, an incorrect string (e.g., `"eur"`, `"Euros"`) will pass silently. Constrain with `Literal["EUR"]` or a currency `Enum`.
- **MEDIUM** — `NormalizedRequest.company_name` defaults to `"Desconocido"` (Spanish for "Unknown"). This default will be stored in memory and used as a dict key, meaning all quotes with missing company names are grouped under a single history bucket. Consider making it `None` and requiring callers to handle the absent value explicitly.
- **MEDIUM** — `StoredQuoteMemory.timestamp` is a plain `str` with no format validation. A `datetime` type (with Pydantic's ISO serialisation) would be more robust and sortable.
- **LOW** — `QuoteResult.version: int = 1` is present but never incremented or checked anywhere in the reviewed files. Document the intended versioning semantics or remove the field to avoid confusion.
- **LOW** — `NormalizedRequest.project_summary` defaults to an empty string `""`. An empty string is falsy but not `None`, making presence checks ambiguous (`if not request.project_summary` catches both). Use `Optional[str] = None` if the field is genuinely optional.

---

## Issues Summary (all severity levels)

| Severity | File | Issue |
|----------|------|-------|
| CRITICAL | shared/config.py | `ODOO_PASSWORD` hardcoded credential in source |
| CRITICAL | shared/config.py | `ODOO_USERNAME` and `ODOO_DB` hardcoded in source |
| CRITICAL | shared/memory_store.py | No file locking — concurrent writes cause silent data loss |
| HIGH | shared/config.py | No env var overrides for Odoo connection settings |
| HIGH | shared/llm.py | Temperature cast to `int`, truncates float values |
| HIGH | shared/llm.py | No env var override for Ollama base URL |
| HIGH | shared/catalog.py | Unmapped requirements silently dropped with no warning |
| HIGH | shared/memory_store.py | `_load_all` swallows all exceptions, can silently wipe history |
| HIGH | shared/memory_store.py | No history size limit — unbounded file growth |
| HIGH | shared/deepeval_eval.py | Default model name duplicated, not imported from `config.py` |
| HIGH | shared/deepeval_eval.py | `get_eval_metrics` return type is untyped `list` |
| HIGH | schemas/budget.py | `QuoteLine.line_total` not validated against `unit_price * quantity` |
| HIGH | schemas/budget.py | `QuoteResult` financial fields have no cross-validation |
| HIGH | schemas/budget.py | `StoredQuoteMemory` uses plain `dict` instead of concrete models |
| MEDIUM | shared/config.py | `ODOO_BASE_URL` hardcoded to localhost with no startup check |
| MEDIUM | shared/llm.py | `int()` cast on env var raises `ValueError` for non-numeric input |
| MEDIUM | shared/llm.py | No Ollama base URL configuration for non-local deployments |
| MEDIUM | shared/catalog.py | Multi-word synonyms with extra inner whitespace will not match |
| MEDIUM | shared/catalog.py | Entire catalog hardcoded; updating requires code changes |
| MEDIUM | shared/memory_store.py | "Last" quote relies on append order, no timestamp-based sort |
| MEDIUM | shared/memory_store.py | `now_iso()` misplaced as a store method; should be a utility |
| MEDIUM | shared/deepeval_eval.py | Metric thresholds (`0.5`) hardcoded with no config point |
| MEDIUM | shared/deepeval_eval.py | Unknown channel types silently fall back to raw JSON |
| MEDIUM | schemas/budget.py | `QuoteResult.currency` is free-text with no validation |
| MEDIUM | schemas/budget.py | `NormalizedRequest.company_name = "Desconocido"` groups all unknown companies together |
| MEDIUM | schemas/budget.py | `StoredQuoteMemory.timestamp` is plain `str` instead of `datetime` |
| LOW | shared/config.py | No `Final` type annotations on module-level constants |
| LOW | shared/llm.py | Return type `ChatOllama` couples callers to the concrete provider |
| LOW | shared/catalog.py | `normalize_requirement` accepts `str` but defensively calls `str()` |
| LOW | shared/catalog.py | Manual deduplication; use `dict.fromkeys()` instead |
| LOW | shared/deepeval_eval.py | Error-case `actual_output` produces meaningless metric scores |
| LOW | shared/deepeval_eval.py | `build_pipeline_test_case` args typed as `dict`, expected keys undocumented |
| LOW | schemas/common.py | No module docstring; Spanish domain terms unexplained |
| LOW | schemas/common.py | `UrgencyLevel` as `Literal` rather than `Enum` |
| LOW | schemas/budget.py | `QuoteResult.version` field semantics undocumented and unused |
| LOW | schemas/budget.py | `NormalizedRequest.project_summary = ""` — ambiguous presence check |
