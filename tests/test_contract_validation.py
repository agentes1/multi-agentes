"""Tests for PipelineContractMetric line structure validation."""
from shared.deepeval_eval import PipelineContractMetric


def test_pipeline_contract_metric_detects_missing_lines_field() -> None:
    """Verify metric rejects quote_result without 'lines' field."""
    metric = PipelineContractMetric(threshold=0.5)
    quote_result = {
        "ok": True,
        "company_name": "ACME",
        "subtotal": 100.0,
        "discount": 10.0,
        "total": 90.0,
        "currency": "USD",
        # missing 'lines'
    }
    score, reason = metric._check_quote_structure(quote_result)
    assert score == 0.0
    assert "missing:" in reason.lower()


def test_pipeline_contract_metric_detects_non_list_lines() -> None:
    """Verify metric rejects lines that is not a list."""
    metric = PipelineContractMetric(threshold=0.5)
    quote_result = {
        "ok": True,
        "company_name": "ACME",
        "lines": "bad string instead of list",
        "subtotal": 100.0,
        "discount": 10.0,
        "total": 90.0,
        "currency": "USD",
    }
    score, reason = metric._check_quote_structure(quote_result)
    assert score == 0.0
    assert "non-empty list" in reason.lower()


def test_pipeline_contract_metric_detects_empty_lines() -> None:
    """Verify metric rejects empty lines list."""
    metric = PipelineContractMetric(threshold=0.5)
    quote_result = {
        "ok": True,
        "company_name": "ACME",
        "lines": [],
        "subtotal": 100.0,
        "discount": 10.0,
        "total": 90.0,
        "currency": "USD",
    }
    score, reason = metric._check_quote_structure(quote_result)
    assert score == 0.0
    assert "non-empty list" in reason.lower()


def test_pipeline_contract_metric_detects_non_dict_line() -> None:
    """Verify metric rejects line item that is not a dict."""
    metric = PipelineContractMetric(threshold=0.5)
    quote_result = {
        "ok": True,
        "company_name": "ACME",
        "lines": ["not a dict"],
        "subtotal": 100.0,
        "discount": 10.0,
        "total": 90.0,
        "currency": "USD",
    }
    score, reason = metric._check_quote_structure(quote_result)
    assert score == 0.0
    assert "not a dict" in reason.lower()


def test_pipeline_contract_metric_detects_missing_line_fields() -> None:
    """Verify metric rejects line with missing required fields (product_code, quantity, unit_price)."""
    metric = PipelineContractMetric(threshold=0.5)
    quote_result = {
        "ok": True,
        "company_name": "ACME",
        "lines": [
            {
                "product_code": "ITEM-001",
                "quantity": 2,
                # missing 'unit_price'
            }
        ],
        "subtotal": 100.0,
        "discount": 10.0,
        "total": 90.0,
        "currency": "USD",
    }
    score, reason = metric._check_quote_structure(quote_result)
    assert score == 0.0
    assert "missing fields" in reason.lower()


def test_pipeline_contract_metric_accepts_valid_lines() -> None:
    """Verify metric accepts properly structured lines."""
    metric = PipelineContractMetric(threshold=0.5)
    quote_result = {
        "ok": True,
        "company_name": "ACME",
        "lines": [
            {"product_code": "ITEM-001", "quantity": 2, "unit_price": 50.0},
            {"product_code": "ITEM-002", "quantity": 1, "unit_price": 100.0},
        ],
        "subtotal": 200.0,
        "discount": 10.0,
        "total": 190.0,
        "currency": "USD",
    }
    score, reason = metric._check_quote_structure(quote_result)
    assert score == 1.0
    assert "valid" in reason.lower() or score > 0
