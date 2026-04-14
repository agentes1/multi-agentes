"""Tests for build_pipeline_test_case output structure.

Replaces the old PipelineContractMetric structural tests.
Verifies that the LLMTestCase produced by build_pipeline_test_case
has the correct shape expected by DeepEval metrics.
"""
from __future__ import annotations

from deepeval.test_case import LLMTestCase

from shared.deepeval_eval import build_pipeline_test_case


def _email_input(subject: str = "CRM", body: str = "Necesito CRM") -> dict:
    return {"channel": "email", "from": "test@acme.com", "subject": subject, "body": body}


def _chat_input(message: str = "Necesito CRM") -> dict:
    return {"channel": "chat", "user_name": "Ana", "company_name": "Acme SL", "message": message}


def _ok_result(final_text: str = "Presupuesto.", quote_result: dict | None = None) -> dict:
    return {
        "ok": True,
        "final_text": final_text,
        "quote_result": quote_result or {
            "company_name": "Acme SL",
            "lines": [{"product_code": "crm_base", "quantity": 1, "unit_price": 1200.0}],
            "subtotal": 1200.0,
            "discount": 120.0,
            "total": 1080.0,
            "currency": "EUR",
        },
    }


def _error_result(error: str = "Error genérico") -> dict:
    return {"ok": False, "error": error}


# ---------------------------------------------------------------------------
# Type and shape
# ---------------------------------------------------------------------------

def test_returns_llm_test_case() -> None:
    tc = build_pipeline_test_case(_email_input(), _ok_result())
    assert isinstance(tc, LLMTestCase)


def test_input_is_non_empty_string() -> None:
    tc = build_pipeline_test_case(_email_input(), _ok_result())
    assert isinstance(tc.input, str)
    assert len(tc.input) > 0


def test_actual_output_is_string() -> None:
    tc = build_pipeline_test_case(_email_input(), _ok_result())
    assert isinstance(tc.actual_output, str)


def test_metadata_has_ok_key() -> None:
    tc = build_pipeline_test_case(_email_input(), _ok_result())
    assert "ok" in tc.additional_metadata


def test_metadata_has_error_key() -> None:
    tc = build_pipeline_test_case(_email_input(), _ok_result())
    assert "error" in tc.additional_metadata


def test_metadata_has_quote_result_key() -> None:
    tc = build_pipeline_test_case(_email_input(), _ok_result())
    assert "quote_result" in tc.additional_metadata


# ---------------------------------------------------------------------------
# ok=True cases
# ---------------------------------------------------------------------------

def test_ok_true_uses_final_text_as_output() -> None:
    tc = build_pipeline_test_case(_email_input(), _ok_result(final_text="Cotización generada."))
    assert tc.actual_output == "Cotización generada."


def test_ok_true_metadata_flag() -> None:
    tc = build_pipeline_test_case(_email_input(), _ok_result())
    assert tc.additional_metadata["ok"] is True


def test_ok_true_quote_result_preserved() -> None:
    qr = {"company_name": "Beta", "lines": [], "subtotal": 0, "discount": 0, "total": 0, "currency": "EUR"}
    tc = build_pipeline_test_case(_email_input(), _ok_result(quote_result=qr))
    assert tc.additional_metadata["quote_result"]["company_name"] == "Beta"


# ---------------------------------------------------------------------------
# ok=False cases
# ---------------------------------------------------------------------------

def test_error_case_uses_error_as_output() -> None:
    tc = build_pipeline_test_case(_email_input(subject="", body=""), _error_result("mcp: timeout"))
    assert "mcp: timeout" in tc.actual_output


def test_error_case_metadata_flag() -> None:
    tc = build_pipeline_test_case(_email_input(), _error_result())
    assert tc.additional_metadata["ok"] is False


def test_error_case_metadata_error_field() -> None:
    tc = build_pipeline_test_case(_email_input(), _error_result("requisitos vacíos"))
    assert tc.additional_metadata["error"] == "requisitos vacíos"


# ---------------------------------------------------------------------------
# Channel-specific input formatting
# ---------------------------------------------------------------------------

def test_email_input_contains_subject() -> None:
    tc = build_pipeline_test_case(_email_input(subject="Dashboard y CRM"), _ok_result())
    assert "Dashboard y CRM" in tc.input


def test_email_input_contains_body() -> None:
    tc = build_pipeline_test_case(_email_input(body="Necesitamos odoo connector"), _ok_result())
    assert "odoo connector" in tc.input


def test_chat_input_contains_company() -> None:
    tc = build_pipeline_test_case(_chat_input(), _ok_result())
    assert "Acme SL" in tc.input


def test_chat_input_contains_message() -> None:
    tc = build_pipeline_test_case(_chat_input(message="Quiero presupuestos con IA"), _ok_result())
    assert "presupuestos con IA" in tc.input
