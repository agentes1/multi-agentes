from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from pipeline import run_pipeline
from shared.deepeval_eval import PipelineContractMetric, build_pipeline_test_case

from .reporting import render_markdown_report, select_winner, summarize_model


_DEFAULT_MODELS_CONFIG = Path("evals/models.yaml")


def _load_models_from_config(config_path: Path) -> list[str]:
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    models = data.get("models", [])
    if not models:
        raise ValueError(f"No models listed in {config_path}. Uncomment at least one model.")
    return [str(m) for m in models]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-model benchmark using project pipeline + DeepEval")
    parser.add_argument("--cases", default="evals/benchmark_cases.jsonl", help="Path to JSONL benchmark cases")
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help="Model names to compare. If omitted, reads from evals/models.yaml",
    )
    parser.add_argument(
        "--models-config",
        default=str(_DEFAULT_MODELS_CONFIG),
        help="Path to models YAML config (default: evals/models.yaml)",
    )
    parser.add_argument("--out-dir", default="evals/reports", help="Directory for JSON/Markdown reports")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="Threshold used by PipelineContractMetric",
    )
    return parser.parse_args()


def _read_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            cases.append(json.loads(stripped))
    return cases


async def _evaluate_single_case(
    *, model: str, case: dict[str, Any], threshold: float
) -> dict[str, Any]:
    case_id = str(case.get("case_id", "unknown"))
    source_input = case["source_input"]
    thread_id = str(case.get("thread_id") or f"eval-{model}-{case_id}")

    started = time.perf_counter()
    try:
        pipeline_result = await run_pipeline(source_input=source_input, thread_id=thread_id, model=model)
    except Exception as exc:
        pipeline_result = {"ok": False, "error": str(exc)}
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000.0

    metric = PipelineContractMetric(threshold=threshold)
    test_case = build_pipeline_test_case(source_input, pipeline_result)
    metric.measure(test_case)

    error_type = ""
    if not pipeline_result.get("ok"):
        error_value = str(pipeline_result.get("error", "unknown"))
        error_type = error_value.split(":", maxsplit=1)[0].strip().lower() or "unknown"

    return {
        "model": model,
        "case_id": case_id,
        "ok": bool(pipeline_result.get("ok", False)),
        "contract_success": bool(metric.is_successful()),
        "deepeval_score": float(metric.score or 0.0),
        "latency_ms": round(elapsed_ms, 2),
        "error_type": error_type,
        "error": pipeline_result.get("error", ""),
        "tags": case.get("tags", []),
    }


async def run_benchmark(
    *, cases: list[dict[str, Any]], models: list[str], threshold: float
) -> dict[str, Any]:
    all_rows: list[dict[str, Any]] = []

    for model in models:
        for case in cases:
            row = await _evaluate_single_case(model=model, case=case, threshold=threshold)
            all_rows.append(row)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        grouped[row["model"]].append(row)

    summaries = {model: summarize_model(rows) for model, rows in grouped.items()}
    winner = select_winner(summaries)

    return {
        "run_id": datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "models": models,
        "cases_total": len(cases),
        "summary_by_model": summaries,
        "winner": winner,
        "raw_results": all_rows,
    }


def _write_reports(result: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = result["run_id"]

    json_path = out_dir / f"multi_model_eval_{run_id}.json"
    markdown_path = out_dir / f"multi_model_eval_{run_id}.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)

    markdown = render_markdown_report(
        run_id=run_id,
        model_summaries=result["summary_by_model"],
        winner=result["winner"],
    )
    with markdown_path.open("w", encoding="utf-8") as handle:
        handle.write(markdown)

    return json_path, markdown_path


def main() -> None:
    args = _parse_args()
    models = args.models or _load_models_from_config(Path(args.models_config))
    print(f"Models to benchmark: {models}")
    cases = _read_cases(Path(args.cases))
    result = asyncio.run(run_benchmark(cases=cases, models=models, threshold=args.threshold))
    json_path, markdown_path = _write_reports(result, Path(args.out_dir))

    print("Benchmark completed")
    print(f"Winner: {result['winner']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
