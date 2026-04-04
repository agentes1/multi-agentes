from deepeval import assert_test

from shared.deepeval_eval import PipelineContractMetric, build_pipeline_test_case


def test_deepeval_pipeline_contract_ok_case() -> None:
    source_input = {
        "channel": "email",
        "from": "cliente@acme.com",
        "subject": "Presupuesto CRM",
        "body": "Necesitamos CRM y facturacion",
    }
    pipeline_result = {
        "ok": True,
        "quote_result": {
            "company_name": "Acme SL",
            "lines": [{"product_code": "crm_base", "quantity": 1, "unit_price": 1000.0}],
            "subtotal": 1000.0,
            "discount": 100.0,
            "total": 900.0,
            "currency": "EUR",
        },
        "final_text": "Presupuesto preliminar para Acme SL por 900 EUR.",
    }

    test_case = build_pipeline_test_case(source_input, pipeline_result)
    metric = PipelineContractMetric(threshold=0.8)
    assert_test(test_case=test_case, metrics=[metric])


def test_deepeval_pipeline_contract_detects_invalid_totals() -> None:
    source_input = {"channel": "email", "body": "Necesitamos CRM"}
    pipeline_result = {
        "ok": True,
        "quote_result": {
            "company_name": "Acme SL",
            "lines": [{"product_code": "crm_base", "quantity": 1, "unit_price": 1000.0}],
            "subtotal": 1000.0,
            "discount": 100.0,
            "total": 1200.0,
            "currency": "EUR",
        },
        "final_text": "Texto final generado.",
    }

    test_case = build_pipeline_test_case(source_input, pipeline_result)
    metric = PipelineContractMetric(threshold=0.8)
    metric.measure(test_case)

    assert metric.is_successful() is False
    assert metric.reason is not None
    assert "invalid" in metric.reason.lower()


def test_deepeval_pipeline_contract_error_shape_case() -> None:
    source_input = {"channel": "email", "subject": "", "body": ""}
    pipeline_result = {
        "ok": False,
        "error": "Entrada vacia",
    }

    test_case = build_pipeline_test_case(source_input, pipeline_result)
    metric = PipelineContractMetric(threshold=0.8)
    assert_test(test_case=test_case, metrics=[metric])
