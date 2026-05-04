from routing.routes import routes
from routing.semantic_router import SemanticTicketRouter, router


def test_budget_route_detects_budget_request() -> None:
    result = router("Queremos un presupuesto para implantar CRM y facturacion en Odoo.")
    assert result.name == "budget"
    assert result.score >= 0.34


def test_budget_route_prioritizes_budget_signals_even_with_greeting() -> None:
    result = router(
        "Asunto: Hola necesito presupuesto\nRemitente: cliente@empresa.com\nMensaje: Quiero precio para implantar CRM en Odoo."
    )
    assert result.name == "budget"
    assert result.score == 1.0


def test_budget_route_detects_implantation_and_training_request() -> None:
    result = router("Necesitamos implantacion de Odoo con CRM y formacion para el equipo.")
    assert result.name == "budget"


def test_budget_route_detects_support_and_custom_development_request() -> None:
    result = router("Queremos presupuesto para soporte mensual y desarrollo a medida.")
    assert result.name == "budget"


def test_budget_route_detects_sales_and_commercial_automation_request() -> None:
    result = router("Buscamos una propuesta para ventas y automatizacion comercial en Odoo.")
    assert result.name == "budget"


def test_sales_route_detects_commercial_process_request() -> None:
    result = router("Queremos mejorar el pipeline comercial y el seguimiento de oportunidades.")
    assert result.name == "sales"


def test_support_incident_routes_to_discard() -> None:
    result = router("Tenemos un error en Odoo y no funciona la facturacion, necesitamos soporte.")
    assert result.name == "discard"


def test_discard_route_handles_general_question() -> None:
    result = router("Hola, que tiempo hace hoy?")
    assert result.name == "discard"


def test_discard_route_handles_non_actionable_message() -> None:
    result = router("Esto es una prueba interna sin peticion concreta.")
    assert result.name == "discard"


class FakeEmbeddingsClient:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        normalized = text.lower()
        if "crm" in normalized or "presupuesto" in normalized or "odoo" in normalized:
            return [1.0, 0.0]
        if "hola" in normalized or "tiempo" in normalized or "prueba" in normalized:
            return [0.0, 1.0]
        return [0.5, 0.5]


def test_router_can_use_embeddings_to_strengthen_budget_match() -> None:
    embeddings_router = SemanticTicketRouter(
        routes,
        embeddings_client=FakeEmbeddingsClient(),
        embeddings_enabled=True,
    )

    result = embeddings_router("Estamos valorando implantar Odoo para CRM comercial.")

    assert result.name == "budget"
    assert result.score >= 0.34
