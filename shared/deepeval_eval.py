from __future__ import annotations

import json
from typing import Any

from deepeval.metrics import AnswerRelevancyMetric, GEval
from deepeval.models import OllamaModel
from deepeval.test_case import LLMTestCase, LLMTestCaseParams


def get_eval_model(model_name: str = "qwen3:4b") -> OllamaModel:
    """Returns a local Ollama model for use as DeepEval evaluator."""
    return OllamaModel(model=model_name)


def get_eval_metrics(model_name: str = "qwen3:4b") -> list:
    """Returns the list of DeepEval pre-built metrics used to evaluate pipeline output.

    Metrics:
    - AnswerRelevancyMetric: measures if the quote text is relevant to the customer request.
    - GEval (Quote Quality): measures if the response is a professional quote in Spanish
      with pricing info and ERP module references.
    """
    eval_model = get_eval_model(model_name)

    answer_relevancy = AnswerRelevancyMetric(
        threshold=0.5,
        model=eval_model,
        include_reason=True,
    )

    quote_quality = GEval(
        name="Quote Quality",
        criteria=(
            "The response is a professional sales quote or budget document written in Spanish. "
            "It must mention at least one specific ERP module or service, include pricing information "
            "(amounts in euros), and directly address the customer's stated needs from the input."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.5,
        model=eval_model,
    )

    return [answer_relevancy, quote_quality]


def build_pipeline_test_case(
    source_input: dict[str, Any], pipeline_result: dict[str, Any]
) -> LLMTestCase:
    """Build a DeepEval LLMTestCase from pipeline I/O.

    Produces a human-readable input string (not raw JSON) so that
    LLM-based metrics can reason about it correctly.
    """
    channel = source_input.get("channel", "unknown")

    if channel == "email":
        input_text = (
            f"Email de {source_input.get('from', 'desconocido')}. "
            f"Asunto: {source_input.get('subject', '')}. "
            f"Mensaje: {source_input.get('body', '')}"
        ).strip()
    elif channel == "chat":
        input_text = (
            f"Chat de {source_input.get('user_name', 'desconocido')} "
            f"en {source_input.get('company_name', 'empresa desconocida')}. "
            f"Mensaje: {source_input.get('message', '')}"
        ).strip()
    else:
        input_text = json.dumps(source_input, ensure_ascii=False)

    actual_output = (
        str(pipeline_result.get("final_text", ""))
        if pipeline_result.get("ok", False)
        else str(pipeline_result.get("error", ""))
    )

    return LLMTestCase(
        input=input_text,
        actual_output=actual_output,
        additional_metadata={
            "ok": bool(pipeline_result.get("ok", False)),
            "error": pipeline_result.get("error", ""),
            "quote_result": pipeline_result.get("quote_result", {}),
        },
    )
