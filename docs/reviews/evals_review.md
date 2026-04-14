# Evaluation System Review

> Reviewed: 2026-04-14 | Reviewer: AI Code Reviewer
> Scope: `evals/` directory — reporting, orchestration, config, benchmark data

---

## evals/reporting.py

### Purpose

Pure computation + rendering module with no I/O side effects. Provides all aggregation helpers and the Markdown renderer used by `run_multi_model_eval.py`. Designed to be easily unit-tested in isolation.

### Metrics used

| Metric | What it measures | Threshold |
|---|---|---|
| `answer_relevancy_score` | How well the agent output addresses the original client request (via DeepEval `AnswerRelevancyMetric`, LLM-as-judge) | ≥ 0.5 |
| `geval_score` | Quote quality: Spanish language, ERP module named, pricing in euros, customer need addressed (via DeepEval `GEval` with custom criteria) | ≥ 0.5 |
| `success_rate` | Proportion of cases where pipeline completed without exception (`ok=True`) | N/A (informational) |
| `latency_p50_ms` | Median end-to-end pipeline latency in ms | N/A (informational) |
| `latency_p95_ms` | 95th-percentile latency — "worst-case normal" | N/A (informational) |
| `error_rate` | Proportion of failed cases, broken down by error type string | N/A (informational) |

### Report structure

The Markdown report produced by `render_markdown_report()` contains:

1. Header with `run_id` and recommended model name.
2. Metrics explanation section — describes each metric, scale, threshold, and winner-selection criteria in human-readable prose.
3. Comparative table — one row per model: success %, relevancy mean, geval mean, p50 ms, p95 ms, error %.
4. Per-model error breakdown — error types and counts. Shows "Sin errores" when none.

A parallel JSON report (raw results + summaries) is also written by `_write_reports()` in `run_multi_model_eval.py`.

### Issues

- **[LOW] No contract/output schema validation in `summarize_model`** — the function assumes keys like `answer_relevancy_score`, `geval_score`, `latency_ms` exist or are `None`. A missing key raises `KeyError` via `float(row[key])` in `compute_mean` (line 26). However, `compute_mean` is not actually called from `summarize_model` — it uses an inline `safe_mean` instead — so this is a latent risk only if `compute_mean` is called externally.
- **[LOW] `compute_latency_percentiles` uses ceiling rank (lines 48-51)** — this is a valid nearest-rank method, but it is not the standard interpolation method used by NumPy/statistics. For very small sample sizes (n=5 in current data), the p95 value collapses to the maximum. Acceptable for now but misleading with small test sets.
- **[LOW] `group_errors` filters on `row.get("ok")` (line 63)** — if `ok` is `False` (boolean), `not row.get("ok")` correctly triggers. But if `ok` is absent (key missing), the row is also treated as an error. Consistent with the rest of the codebase but undocumented.
- **[LOW] `render_markdown_report` is a single 100-line function** — exceeds the 50-line soft limit from coding style rules. Consider extracting `_render_metrics_legend()` and `_render_comparison_table()` as private helpers.

---

## evals/run_multi_model_eval.py

### Purpose

Entry point and async orchestrator for the multi-model benchmark. Loads test cases from JSONL, iterates over each model×case combination, calls the production pipeline, optionally runs LLM evaluation metrics, aggregates results, picks a winner, and writes both JSON and Markdown reports.

### Evaluation flow

```
CLI args / models.yaml
        │
        ▼
_load_models_from_config()  ──►  list[str] model names
_read_cases()               ──►  list[dict] benchmark cases
        │
        ▼
run_benchmark()
  for model in models:
    get_eval_metrics(model_name=model)      # DeepEval metrics instantiated once per model
    for case in cases:
      _evaluate_single_case(...)
        ├── run_pipeline(source_input, thread_id, model)   # production pipeline, async
        ├── if ok: build_pipeline_test_case(...)
        │         metric.a_measure(test_case) for each metric
        └── returns row dict {model, case_id, ok, scores, latency_ms, error_type, ...}
        │
        ▼
  group rows by model → summarize_model() → select_winner()
        │
        ▼
_write_reports()  →  JSON + Markdown to evals/reports/
```

### Models configured

Active models in `evals/models.yaml` (4 local Ollama models):

| Model | Size | Notes |
|---|---|---|
| `mistral` | 4.4 GB | Mistral 7B, strong reasoning |
| `llama3.2` | 2.0 GB | Meta Llama 3.2 3B, lightweight |
| `qwen3:4b` | 2.5 GB | Fast, good quality |
| `gemma3:4b` | 3.3 GB | Google Gemma 3 4B |

Commented-out options include llama3.1/3.3, mistral-nemo, qwen2.5, qwen3:8b, phi4, phi4-mini, gemma3:12b.

### Issues

- **[CRITICAL] Sequential evaluation — no concurrency between models or cases** — `run_benchmark()` uses a plain `for model in models: for case in cases:` loop (lines 117-123). Each `_evaluate_single_case` call is `await`-ed one at a time. With 4 models × 5 cases = 20 calls, and each LLM call taking several seconds, a full run can take minutes. `asyncio.gather` or `asyncio.TaskGroup` over cases (per model) would give substantial speedup with zero correctness risk.
- **[HIGH] Metric exceptions are silently swallowed as score=0.0** — lines 93-95: any exception during `metric.a_measure()` sets the score to `0.0` without logging. A model that consistently causes DeepEval to crash will appear to score 0.0 on quality metrics rather than being flagged as broken. At minimum, the exception should be logged to stderr.
- **[HIGH] `get_eval_metrics(model_name=model)` uses the pipeline model as the judge** — the same Ollama model under test is used as the LLM judge for its own output. This creates a self-evaluation bias: a model that produces outputs matching its own style will score higher. Ideally the judge should be a fixed, separate model.
- **[MEDIUM] `thread_id` is derived from model name + case_id (line 67)** — if the pipeline stores conversation state by `thread_id`, re-running the benchmark will reuse the same thread IDs and may retrieve stale memory from a prior run. This can cause non-deterministic results across runs.
- **[MEDIUM] No retry logic for pipeline failures** — transient errors (network timeout, Ollama process crash) are recorded as hard failures. A single retry with exponential backoff would reduce noise in results.
- **[MEDIUM] `run_id` is generated at benchmark completion time (line 133)**, not at start — the `run_id` timestamp reflects when results were assembled, not when the run began. This is mildly misleading for long runs.
- **[LOW] `print()` used for progress/completion output (lines 171-174)** — should use `logging` module per Python coding style rules.
- **[LOW] No `--concurrency` flag** — adding a concurrency limit would allow safe parallelism without overloading a local Ollama instance.
- **[LOW] `_evaluate_single_case` has no timeout guard on `run_pipeline`** — a hung Ollama call will block the entire benchmark indefinitely.

---

## evals/models.yaml

### Purpose

Declarative list of Ollama model names to include in the benchmark. Single source of truth for which models are active. Can be overridden at runtime via `--models` CLI flag.

### Issues

- **[LOW] No version pinning** — `mistral`, `llama3.2`, etc. are tag-less references. `ollama pull mistral` will pull the latest tag, so results may not be reproducible across machines or time. Consider using digest-pinned tags (e.g., `mistral:7b-instruct-v0.3-q4_K_M`) for stable benchmarks.
- **[LOW] No minimum-resource annotation** — the file lists sizes as comments but does not enforce memory checks before running. On a machine with limited VRAM, loading a 4.4 GB model after a 3.3 GB model may cause OOM errors mid-benchmark.

---

## evals/__init__.py

### Purpose

Empty init file (1 line). Makes `evals/` a Python package so that `from .reporting import ...` relative imports work in `run_multi_model_eval.py`.

### Issues

- None. Intentionally minimal.

---

## evals/benchmark_cases.jsonl

### Structure of test cases

Each line is a JSON object with this shape:

```json
{
  "case_id": "email_ok_001",
  "thread_id": "eval-email-001",
  "source_input": {
    "channel": "email" | "chat",
    "from": "...",          // email only
    "subject": "...",       // email only
    "body": "...",          // email only
    "user_name": "...",     // chat only
    "company_name": "...",  // chat only
    "message": "..."        // chat only
  },
  "tags": ["happy_path" | "invalid_input", "email" | "chat"]
}
```

### Count / coverage

| Tag | Count |
|---|---|
| `happy_path` + `email` | 2 |
| `happy_path` + `chat` | 1 |
| `invalid_input` (email with empty body) | 1 |
| `invalid_input` (chat with empty message) | 1 |
| **Total** | **5** |

### Issues

- **[HIGH] Only 5 test cases — statistically insufficient** — with n=5, all aggregate metrics (mean relevancy, mean geval, latency percentiles) have extremely high variance. p95 latency collapses to the single maximum value. A meaningful benchmark requires at minimum 20-50 cases per category. The winner selection result is essentially noise at this sample size.
- **[HIGH] No negative/adversarial cases beyond empty inputs** — the only "bad" cases test for empty body/message. Missing: malformed JSON fields, non-Spanish input, very long inputs, injection attempts, competitor-product mentions, multi-product complex requests.
- **[MEDIUM] No expected output / ground truth** — cases contain only input. There is no `expected_output` or `reference_answer` field. This prevents using reference-based metrics (e.g., `FaithfulnessMetric`, BLEU, ROUGE) and makes it impossible to detect regressions where output changes but LLM judge scores stay the same.
- **[MEDIUM] No multi-turn / context cases** — all cases are single-turn. The pipeline likely supports multi-turn conversations but the benchmark never exercises them.
- **[LOW] `thread_id` is hardcoded** — see the concern noted in `run_multi_model_eval.py` about stale conversation memory being reused across benchmark runs.

---

## Issues Summary

| Severity | File | Issue |
|---|---|---|
| CRITICAL | run_multi_model_eval.py | Sequential evaluation — no async concurrency between cases/models |
| HIGH | run_multi_model_eval.py | Metric exceptions silently produce score=0.0 (no logging) |
| HIGH | run_multi_model_eval.py | Pipeline model used as its own LLM judge (self-evaluation bias) |
| HIGH | benchmark_cases.jsonl | Only 5 test cases — results are statistically meaningless |
| HIGH | benchmark_cases.jsonl | No adversarial/edge cases beyond empty inputs |
| MEDIUM | run_multi_model_eval.py | Hardcoded thread_ids risk reusing stale pipeline memory across runs |
| MEDIUM | run_multi_model_eval.py | No retry logic for transient pipeline failures |
| MEDIUM | run_multi_model_eval.py | `run_id` timestamp recorded at end of run, not start |
| MEDIUM | benchmark_cases.jsonl | No expected output / ground truth field |
| MEDIUM | benchmark_cases.jsonl | No multi-turn conversation test cases |
| LOW | run_multi_model_eval.py | `print()` used instead of `logging` module |
| LOW | run_multi_model_eval.py | No timeout guard on `run_pipeline` calls |
| LOW | run_multi_model_eval.py | No `--concurrency` CLI flag |
| LOW | reporting.py | `render_markdown_report` exceeds 50-line function guideline |
| LOW | reporting.py | `compute_mean` has a latent `KeyError` path if called with missing keys |
| LOW | reporting.py | p95 with n=5 collapses to max value — misleading label |
| LOW | models.yaml | No model version/digest pinning — not reproducible across environments |
| LOW | models.yaml | No VRAM/resource guard before loading models sequentially |
