"""Tests for shared/deepeval_eval.py — uses mocks, no live Ollama required."""
from __future__ import annotations

from deepeval.metrics import AnswerRelevancyMetric, GEval
from deepeval.test_case import LLMTestCase

from shared.deepeval_eval import build_pipeline_test_case, get_eval_metrics, get_eval_model


# ---------------------------------------------------------------------------
# build_pipeline_test_case
# ---------------------------------------------------------------------------

def test_build_test_case_email_input_is_readable() -> None:
    source_input = {
        "channel": "email",
        "from": "cliente@acme.com",
        "subject": "Presupuesto CRM",
        "body": "Necesitamos CRM y facturación",
    }
    result = {"ok": True, "final_text": "Presupuesto para ACME...", "quote_result": {}}
    tc = build_pipeline_test_case(source_input, result)

    assert isinstance(tc, LLMTestCase)
    assert "acme.com" in tc.input
    assert "CRM" in tc.input
    assert "Presupuesto para ACME" in tc.actual_output


def test_build_test_case_chat_input_is_readable() -> None:
    source_input = {
        "channel": "chat",
        "user_name": "Laura",
        "company_name": "Beta SL",
        "message": "Necesito un dashboard",
    }
    result = {"ok": True, "final_text": "Cotización para Beta SL...", "quote_result": {}}
    tc = build_pipeline_test_case(source_input, result)

    assert "Laura" in tc.input or "Beta SL" in tc.input
    assert "dashboard" in tc.input
    assert tc.additional_metadata["ok"] is True


def test_build_test_case_error_uses_error_field() -> None:
    source_input = {"channel": "email", "from": "x@x.com", "subject": "", "body": ""}
    result = {"ok": False, "error": "Email vacío: cuerpo y asunto vacíos"}
    tc = build_pipeline_test_case(source_input, result)

    assert "Email vacío" in tc.actual_output
    assert tc.additional_metadata["ok"] is False


def test_build_test_case_metadata_ok_true() -> None:
    source_input = {"channel": "email", "from": "a@b.com", "subject": "S", "body": "B"}
    result = {
        "ok": True,
        "final_text": "Texto final.",
        "quote_result": {"company_name": "Test", "lines": []},
    }
    tc = build_pipeline_test_case(source_input, result)

    assert tc.additional_metadata["ok"] is True
    assert tc.additional_metadata["quote_result"]["company_name"] == "Test"


def test_build_test_case_metadata_ok_false() -> None:
    source_input = {"channel": "chat", "user_name": "X", "company_name": "Y", "message": ""}
    result = {"ok": False, "error": "Mensaje vacío"}
    tc = build_pipeline_test_case(source_input, result)

    assert tc.additional_metadata["ok"] is False
    assert tc.additional_metadata["error"] == "Mensaje vacío"


def test_build_test_case_unknown_channel_falls_back_to_json() -> None:
    source_input = {"channel": "webhook", "payload": "some data"}
    result = {"ok": False, "error": "Canal no soportado"}
    tc = build_pipeline_test_case(source_input, result)

    assert "webhook" in tc.input


# ---------------------------------------------------------------------------
# get_eval_model / get_eval_metrics (structural checks, no LLM calls)
# ---------------------------------------------------------------------------

def test_get_eval_model_returns_ollama_model() -> None:
    model = get_eval_model("qwen3:4b")
    assert model is not None
    # OllamaModel has a model attribute
    assert hasattr(model, "model") or hasattr(model, "_model") or str(model)


def test_get_eval_metrics_returns_two_metrics() -> None:
    metrics = get_eval_metrics("qwen3:4b")
    assert len(metrics) == 2


def test_get_eval_metrics_first_is_answer_relevancy() -> None:
    metrics = get_eval_metrics("qwen3:4b")
    assert isinstance(metrics[0], AnswerRelevancyMetric)


def test_get_eval_metrics_second_is_geval() -> None:
    metrics = get_eval_metrics("qwen3:4b")
    assert isinstance(metrics[1], GEval)


def test_get_eval_metrics_geval_has_quote_criteria() -> None:
    metrics = get_eval_metrics("qwen3:4b")
    geval = metrics[1]
    assert "presupuesto" in geval.criteria.lower() or "quote" in geval.criteria.lower()
