from evals.reporting import (
    compute_latency_percentiles,
    compute_rate,
    group_errors,
    select_winner,
    summarize_model,
)


def test_compute_rate_handles_normal_and_empty_inputs() -> None:
    rows = [
        {"ok": True},
        {"ok": True},
        {"ok": True},
        {"ok": False},
    ]

    assert compute_rate(rows, "ok") == 0.75
    assert compute_rate([], "ok") == 0.0


def test_compute_latency_percentiles_returns_expected_p50_p95() -> None:
    rows = [
        {"latency_ms": 100},
        {"latency_ms": 200},
        {"latency_ms": 300},
        {"latency_ms": 400},
        {"latency_ms": 500},
    ]

    result = compute_latency_percentiles(rows)
    assert result[50] == 300
    assert result[95] == 500


def test_group_errors_counts_only_failed_rows_by_error_type() -> None:
    rows = [
        {"ok": False, "error_type": "timeout"},
        {"ok": False, "error_type": "timeout"},
        {"ok": False, "error_type": "rate_limit"},
        {"ok": True, "error_type": None},
    ]

    assert group_errors(rows) == {"timeout": 2, "rate_limit": 1}


def test_summarize_model_builds_consistent_aggregate_report() -> None:
    rows = [
        {"ok": True, "contract_success": True, "deepeval_score": 1.0, "latency_ms": 100.0, "error_type": ""},
        {"ok": True, "contract_success": False, "deepeval_score": 0.5, "latency_ms": 300.0, "error_type": ""},
        {"ok": False, "contract_success": False, "deepeval_score": 0.2, "latency_ms": 500.0, "error_type": "timeout"},
    ]

    summary = summarize_model(rows)

    assert summary["total_cases"] == 3
    assert summary["success_rate"] == 2 / 3
    assert summary["contract_pass_rate"] == 1 / 3
    assert summary["deepeval_score_mean"] > 0
    assert summary["latency_p50_ms"] == 300.0
    assert summary["latency_p95_ms"] == 500.0
    assert summary["errors"]["total"] == 1
    assert summary["errors"]["types"] == {"timeout": 1}


def test_select_winner_applies_score_then_latency_then_name_tiebreak() -> None:
    model_summaries = {
        "qwen2.5": {
            "contract_pass_rate": 0.9,
            "deepeval_score_mean": 0.8,
            "latency_p50_ms": 600,
        },
        "qwen3": {
            "contract_pass_rate": 0.9,
            "deepeval_score_mean": 0.8,
            "latency_p50_ms": 500,
        },
        "llama3": {
            "contract_pass_rate": 0.85,
            "deepeval_score_mean": 0.9,
            "latency_p50_ms": 300,
        },
    }

    assert select_winner(model_summaries) == "qwen3"

    tie_summaries = {
        "a-model": {"contract_pass_rate": 0.9, "deepeval_score_mean": 0.8, "latency_p50_ms": 500},
        "b-model": {"contract_pass_rate": 0.9, "deepeval_score_mean": 0.8, "latency_p50_ms": 500},
    }
    assert select_winner(tie_summaries) == "a-model"
