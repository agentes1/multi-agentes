from __future__ import annotations

import json
from typing import Any

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase, LLMTestCaseParams


class PipelineContractMetric(BaseMetric):
    _required_params = [LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT]

    def __init__(
        self,
        threshold: float = 0.8,
        include_reason: bool = True,
        async_mode: bool = True,
        strict_mode: bool = False,
    ) -> None:
        self.threshold = threshold
        self.include_reason = include_reason
        self.async_mode = async_mode
        self.strict_mode = strict_mode
        self.verbose_mode = False
        self.score = None
        self.reason = None
        self.success = None
        self.error = None
        self.evaluation_model = None
        self.evaluation_cost = None
        self.verbose_logs = None
        self.score_breakdown = None
        self.skipped = False
        self.model = None
        self.using_native_model = None

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        try:
            metadata = test_case.additional_metadata or {}
            components: list[float] = []
            reasons: list[str] = []

            ok_flag = bool(metadata.get("ok"))
            if ok_flag:
                components.append(1.0)
                reasons.append("Pipeline status: ok=true")

                quote_result = metadata.get("quote_result") or {}
                structure_score, structure_reason = self._check_quote_structure(quote_result)
                components.append(structure_score)
                reasons.append(structure_reason)

                final_text = str(test_case.actual_output or "").strip()
                components.append(1.0 if final_text else 0.0)
                reasons.append("Final text present" if final_text else "Final text missing")
            else:
                error_text = str(metadata.get("error") or "").strip()
                components.append(1.0 if error_text else 0.0)
                reasons.append(
                    "Error shape valid (ok=false and error present)"
                    if error_text
                    else "Error shape invalid (ok=false but error missing)"
                )

            score = sum(components) / len(components)
            if self.strict_mode and score < self.threshold:
                score = 0.0

            self.score = score
            self.success = self.score >= self.threshold
            self.reason = "\n".join(reasons) if self.include_reason else None
            return self.score
        except Exception as exc:
            self.error = str(exc)
            self.success = False
            raise

    async def a_measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        if self.error is not None:
            self.success = False
        else:
            self.success = bool(self.score is not None and self.score >= self.threshold)
        return self.success

    @property
    def __name__(self) -> str:
        return "Pipeline Contract"

    @staticmethod
    def _check_quote_structure(quote_result: dict[str, Any]) -> tuple[float, str]:
        required_fields = ["company_name", "lines", "subtotal", "discount", "total", "currency"]
        missing = [field for field in required_fields if field not in quote_result]
        if missing:
            return 0.0, f"Quote structure invalid, missing: {missing}"

        lines = quote_result.get("lines")
        if not isinstance(lines, list) or len(lines) == 0:
            return 0.0, "Quote lines must be a non-empty list"

        line_required = ["product_code", "quantity", "unit_price"]
        for idx, line in enumerate(lines):
            if not isinstance(line, dict):
                return 0.0, f"Line {idx} is not a dict: {type(line)}"
            missing_in_line = [field for field in line_required if field not in line]
            if missing_in_line:
                return 0.0, f"Line {idx} missing fields: {missing_in_line}"

        subtotal = quote_result.get("subtotal")
        discount = quote_result.get("discount")
        total = quote_result.get("total")
        if not all(isinstance(value, (int, float)) for value in (subtotal, discount, total)):
            return 0.0, "Quote structure invalid, totals are not numeric"

        expected_total = float(subtotal) - float(discount)
        if abs(float(total) - expected_total) > 0.05:
            return 0.0, (
                "Quote totals invalid: "
                f"subtotal={subtotal}, discount={discount}, total={total}, expected={expected_total}"
            )

        return 1.0, "Quote structure and totals are valid"


def build_pipeline_test_case(source_input: dict[str, Any], pipeline_result: dict[str, Any]) -> LLMTestCase:
    """Build a deterministic DeepEval test case from pipeline I/O."""
    actual_output = (
        str(pipeline_result.get("final_text", ""))
        if pipeline_result.get("ok", False)
        else str(pipeline_result.get("error", ""))
    )

    return LLMTestCase(
        input=json.dumps(source_input, ensure_ascii=False),
        actual_output=actual_output,
        additional_metadata={
            "ok": bool(pipeline_result.get("ok", False)),
            "error": pipeline_result.get("error", ""),
            "quote_result": pipeline_result.get("quote_result", {}),
        },
    )
