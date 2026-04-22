from routing.semantic_router import router


def test_budget_route_detects_budget_request() -> None:
    result = router("Queremos un presupuesto para implantar CRM y facturacion en Odoo.")
    assert result.name == "budget"
    assert result.score >= 0.34


def test_issue_route_detects_support_incident() -> None:
    result = router("Tenemos un error en Odoo y no funciona la facturacion, necesitamos soporte.")
    assert result.name == "issue"
    assert result.score >= 0.34


def test_discard_route_handles_non_actionable_message() -> None:
    result = router("Hola, gracias por la informacion. Era solo una prueba.")
    assert result.name == "discard"
