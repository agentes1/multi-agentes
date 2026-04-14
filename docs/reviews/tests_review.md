# Test Suite Review

> Reviewed: 2026-04-14
> Scope: `tests/` (7 files) + root-level `test_odoo_integration.py`

---

## Overview

### Total test files: 8

| File | Domain | Approach | ~Tests |
|---|---|---|---|
| `tests/test_api.py` | FastAPI `/process` endpoint | Integration, fully mocked | 2 |
| `tests/test_budget_agent.py` | Budget agent graph error paths | Unit, mocked dependencies | 2 |
| `tests/test_contract_validation.py` | `build_pipeline_test_case` output shape | Unit, pure Python | 16 |
| `tests/test_deepeval_eval.py` | `build_pipeline_test_case` + eval model/metrics | Unit, no live LLM | 11 |
| `tests/test_intake_agent.py` | Intake agent → real Odoo ticket creation | Integration, **live Odoo required** | 1 |
| `tests/test_multi_model_eval_reporting.py` | Reporting functions (rate, latency, winner) | Unit, pure Python | 4 |
| `tests/test_odoo_api_wrapper.py` | OdooAPIWrapper CRUD + helpdesk | Integration, **live Odoo required** | 17 |
| `test_odoo_integration.py` (root) | MCPBudgetService smoke test | **Script, not a test** | 0 (not pytest) |

### Test approach per domain

- **Agent graphs** (intake, budget): mix of mocked unit tests (budget errors) and one live integration test (intake). Happy path for both graphs is untested with mocks.
- **API layer**: mocked end-to-end via `ASGITransport`. Only 2 cases.
- **Eval / reporting**: well-covered pure-unit tests; no live LLM calls needed.
- **Odoo integration**: all live, requires real credentials and a running Odoo instance. No mock-based unit tests for `OdooAPIWrapper`.

---

## Per-file Analysis

### `tests/test_api.py`

**What it tests:** FastAPI `/process` endpoint — happy path email and empty-body 400 rejection.

**Approach:** Async integration test with `AsyncClient` + `ASGITransport`. Full pipeline mocked at dependency injection level (`pipeline.build_intake_deps`, `pipeline.build_budget_deps`).

**Test count:** 2

**Coverage gaps:**
- Only one valid input variant tested; no chat/webhook channels.
- No test for partial missing fields (e.g. missing `body` key, not just empty string).
- 400 vs 422 distinction: the test asserts `status_code == 400` for an empty body but FastAPI validation errors return 422 by default — this assertion may fail if Pydantic rejects the payload first (see Issues).
- No test for 500 server errors (e.g. MCP failure propagation through the API).
- No test for the response structure beyond `ok` and `company_name`.

**Issues:**
- **HIGH** — `test_process_email_vacio_devuelve_422`: test name says 422 but assertion checks for `400`. If the validation happens in Pydantic (empty string still passes the model) and the error is raised in the pipeline, a `400` could be correct, but the mismatch between the name and the assertion is misleading and fragile.

---

### `tests/test_budget_agent.py`

**What it tests:** Budget agent graph error paths — empty requirements list and failing MCP service.

**Approach:** Unit tests against `build_budget_graph()` with fully mocked `BudgetDependencies`. Uses `InMemorySaver` via `thread_id`.

**Test count:** 2

**Coverage gaps:**
- No happy-path test (valid requirements + working MCP → successful quote generation).
- No test for partial quote (MCP returns lines with `total: 0`).
- No test for `retrieve_memory_node` behaviour with non-zero `quote_count` history.
- No test for `generate_text_node` LLM failure.
- No test that `append_quote` is called after a successful run.

**Issues:**
- **MEDIUM** — Only error paths are tested; a regression in the happy-path flow would go undetected.
- **LOW** — `MockMCPService` returns an empty `lines: []` quote, which may be a near-error state but is not asserted on.

---

### `tests/test_contract_validation.py`

**What it tests:** Shape and content of `LLMTestCase` produced by `build_pipeline_test_case` (from `shared/deepeval_eval.py`).

**Approach:** Pure unit tests, no external dependencies, no LLM calls.

**Test count:** 16

**Coverage gaps:**
- No test for an unknown/unsupported channel other than "webhook" (covered in `test_deepeval_eval.py`).
- No test for `quote_result` being `None` when `ok=True`.
- No test for very long inputs (potential truncation issues).

**Issues:**
- **LOW** — Significant overlap with `test_deepeval_eval.py`; both files test `build_pipeline_test_case` with nearly identical cases. This creates maintenance duplication. Consider consolidating into one file.

---

### `tests/test_deepeval_eval.py`

**What it tests:** `build_pipeline_test_case`, `get_eval_model`, and `get_eval_metrics` from `shared/deepeval_eval.py`.

**Approach:** Unit tests, no live Ollama/LLM calls. Structural checks on metric types and attributes.

**Test count:** 11

**Coverage gaps:**
- `get_eval_model` test (`test_get_eval_model_returns_ollama_model`) uses a loose assertion: `hasattr(model, "model") or hasattr(model, "_model") or str(model)` — `str(model)` is always truthy and makes the test vacuous (see Issues).
- No test for `get_eval_metrics` with an invalid/empty model name.
- No test asserting `threshold` values on metrics.

**Issues:**
- **HIGH** — `test_get_eval_model_returns_ollama_model`: the final `or str(model)` condition is always `True` for any non-None object, making the assertion meaningless. The test can never fail regardless of what `get_eval_model` returns.
- **LOW** — Duplication with `test_contract_validation.py` (see note above).

---

### `tests/test_intake_agent.py`

**What it tests:** Full intake agent pipeline — email input → LLM normalization → helpdesk ticket creation in real Odoo.

**Approach:** Integration test, marked `@pytest.mark.integration` and `@pytest.mark.asyncio`. Requires live Odoo credentials from `shared/config`.

**Test count:** 1

**Coverage gaps:**
- No mocked unit test for the intake graph (happy path without Odoo).
- No test for chat channel input.
- No test for `ticket_type == "quote"` (only `"issue"` is covered).
- No test for intake graph when LLM returns `missing_information` list (clarification flow).
- No test for Odoo connection failure (error propagation).
- Cleanup in `finally` block only prints `'fin'` — the created ticket is **never deleted** after the test.

**Issues:**
- **CRITICAL** — `finally` block does `print('fin')` instead of deleting the ticket. Every test run creates a permanent garbage ticket in the real Odoo instance. Compare with `test_odoo_api_wrapper.py` which correctly calls `unlink`.
- **HIGH** — Single test covers a wide assertion set; if the Odoo team/type/category names change, the test fails with an opaque assertion error rather than a descriptive message.
- **HIGH** — No mock-based counterpart: CI pipelines without Odoo access cannot run any intake agent test.
- **MEDIUM** — `_base_config` does not set `thread_id`; if the graph uses `InMemorySaver` this may cause issues in repeated runs within the same process.

---

### `tests/test_multi_model_eval_reporting.py`

**What it tests:** Pure reporting utility functions: `compute_rate`, `compute_latency_percentiles`, `group_errors`, `summarize_model`, `select_winner`.

**Approach:** Pure unit tests, no external dependencies.

**Test count:** 4 (plus sub-assertions within each test)

**Coverage gaps:**
- `compute_latency_percentiles`: no test for a single-element list or list with identical values.
- `select_winner`: no test for a single-model dict (edge case: winner should be that model).
- `select_winner`: no test when all models have `success_rate == 0`.
- `summarize_model`: no test when all rows have `ok=False` (means / scores should be `None` or 0).
- `group_errors`: no test for rows where `error_type` key is missing entirely (KeyError risk).

**Issues:**
- **MEDIUM** — `test_select_winner_applies_score_then_latency_then_name_tiebreak`: comment says "score then latency then name" but the first priority in the implementation is `success_rate`. The test name describes the old behavior; may confuse future maintainers.
- **LOW** — Tests are grouped into single functions with multiple assertions; a failure stops on the first failing assert and hides the rest.

---

### `tests/test_odoo_api_wrapper.py`

**What it tests:** `OdooAPIWrapper` CRUD operations for products, contacts, search, and helpdesk tickets.

**Approach:** Integration tests against a **live Odoo** instance. No mocking. Module-level `wrapper` instantiation at import time — if credentials are missing, all tests fail with a confusing import-time error.

**Test count:** 17

**Coverage gaps:**
- No test for authentication failure (wrong password/db).
- No test for `get_product` / `get_contact` with a non-existent ID (already covered by `test_delete_*` tests indirectly, but not explicitly as a standalone case).
- No test for `create_helpdesk_ticket` with invalid `team_id` (foreign key violation handling).
- No test for `get_tag_ids_by_names` with entirely unknown tag names (should return empty list or raise?).
- `get_helpdesk_ticket` (singular, used in `test_intake_agent.py`) is not tested here.

**Issues:**
- **HIGH** — Module-level instantiation `wrapper = OdooAPIWrapper(...)` at the top of the file means importing the test module with invalid/missing credentials will raise immediately, crashing the entire pytest collection — not just skipping these tests.
- **HIGH** — No `pytest.mark.integration` marker. These tests will run in any `pytest` invocation even without Odoo available, causing CI failures.
- **MEDIUM** — Ticket cleanup in `test_create_helpdesk_ticket_simple` and `test_create_helpdesk_ticket_full` calls `wrapper._models.execute_kw(...)` directly, accessing private attributes. Should use a public `delete_helpdesk_ticket` method or the wrapper's own API.
- **MEDIUM** — `test_list_helpdesk_tickets` creates a ticket for listing but never deletes it (no cleanup).
- **LOW** — Tests are not isolated from each other: if `test_create_product` fails mid-way, subsequent tests may find stale data.

---

### `test_odoo_integration.py` (root level)

**What it tests:** MCPBudgetService smoke test — calls `get_budget_context` and prints results.

**Approach:** **This is a script, not a pytest test.** It has no assertions and is only runnable via `python test_odoo_integration.py`. The file defines no `test_*` functions.

**Test count:** 0

**Issues:**
- **HIGH** — Not a test file. Has no assertions. Will not be collected or run by pytest. Provides zero automated coverage of `MCPBudgetService`. Should be converted to a proper pytest integration test with assertions, or moved to a `scripts/` directory with a clear name.

---

## Coverage Gaps (Global)

The following areas have **no automated test coverage** at all:

- `MCPBudgetService` (`services/mcp_budget.py`) — only has a manual script, no real tests.
- `pipeline.py` happy path without going through the API layer (e.g. direct `run_pipeline()` call).
- Intake agent graph happy path with mocked dependencies (non-integration).
- Budget agent graph happy path (valid requirements + working MCP).
- Chat channel end-to-end through the API (`/process` with `channel: "chat"`).
- `shared/config.py` — validation of required environment variables at startup.
- `shared/memory_store.py` — no tests for the actual in-memory or persistent store.
- Multi-model eval runner (`evals/runner.py` or equivalent) — harness that drives the benchmarks.
- Error message content validation (tests only assert `error is not None` or `"mcp" in error.lower()`).
- Concurrent requests to the API (race conditions in shared state).
- `select_winner` in `evals/reporting.py` with a single model, all-fail scenario, or empty dict.

---

## Issues Summary

| Severity | File | Issue |
|---|---|---|
| CRITICAL | `tests/test_intake_agent.py` | `finally` block does `print('fin')` instead of deleting the Odoo ticket — permanent garbage data on every run |
| HIGH | `tests/test_api.py` | Test named `test_process_email_vacio_devuelve_422` but asserts `status_code == 400` |
| HIGH | `tests/test_deepeval_eval.py` | `test_get_eval_model_returns_ollama_model` assertion is vacuously true (`or str(model)`) |
| HIGH | `tests/test_intake_agent.py` | No mock-based counterpart; CI without Odoo cannot run any intake agent test |
| HIGH | `tests/test_odoo_api_wrapper.py` | Module-level `OdooAPIWrapper(...)` instantiation crashes pytest collection on missing credentials |
| HIGH | `tests/test_odoo_api_wrapper.py` | Missing `@pytest.mark.integration` — runs unconditionally in CI |
| HIGH | `test_odoo_integration.py` (root) | Not a test file — no assertions, never collected by pytest, provides zero coverage |
| MEDIUM | `tests/test_budget_agent.py` | Only error paths tested; happy path for budget graph is untested |
| MEDIUM | `tests/test_multi_model_eval_reporting.py` | Test name describes old priority order; misleads future maintainers |
| MEDIUM | `tests/test_odoo_api_wrapper.py` | `test_list_helpdesk_tickets` creates a ticket but never deletes it |
| MEDIUM | `tests/test_odoo_api_wrapper.py` | Cleanup uses private `_models`, `_db`, `_uid`, `_password` attributes |
| LOW | `tests/test_contract_validation.py` | Significant duplication with `test_deepeval_eval.py` for `build_pipeline_test_case` |
| LOW | `tests/test_multi_model_eval_reporting.py` | Single-function multi-assert style hides downstream failures |
