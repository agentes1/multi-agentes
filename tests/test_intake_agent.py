import uuid

import pytest

from agents.intake_agent.dependencies import TicketAgentDependencies
from agents.intake_agent.graph import build_ticket_graph
from odoo.api import OdooAPIWrapper
from odoo.service import OdooService
from odoo.helpers import Table
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD


class MockLLM:
    """Mock LLM that returns the provided JSON for normalize_email_node
    and returns no tool_calls for enrich_context_node."""

    def __init__(self, content: str):
        self._content = content

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        class _Response:
            content = self._content
            tool_calls = []
        return _Response()


def _build_deps(mock_json: str) -> TicketAgentDependencies:
    wrapper = OdooAPIWrapper(
        url=ODOO_BASE_URL,
        username=ODOO_USERNAME,
        password=ODOO_PASSWORD,
        db=ODOO_DB,
    )
    return TicketAgentDependencies(
        llm=MockLLM(mock_json),
        odoo_service=OdooService(wrapper),
    )


def _base_config(deps: TicketAgentDependencies) -> dict:
    return {
        "configurable": {
            "deps": deps,
            "thread_id": f"test-intake-agent-{uuid.uuid4()}",
        }
    }


def _cleanup(deps: TicketAgentDependencies, ticket_id: int | None, partner_id: int | None) -> None:
    if ticket_id:
        try:
            deps.odoo_service._wrapper.delete(Table.Ticket, [ticket_id])
        except Exception:
            pass
    if partner_id:
        try:
            deps.odoo_service._wrapper.delete(Table.Contact, [partner_id])
        except Exception:
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_email_crea_ticket_en_odoo():
    graph = build_ticket_graph()
    deps = _build_deps('{"title": "Error en CRM", "description": "No podemos crear oportunidades en Odoo CRM", "customer_name": "Acme SL", "customer_email": "cliente@acme.com"}')

    result = await graph.ainvoke(
        {
            "email_subject": "Incidencia con CRM",
            "email_body": "Hola, somos Acme SL. Tenemos un error al crear oportunidades en Odoo CRM.",
            "sender_email": "cliente@acme.com",
            "sender_name": "Acme SL",
        },
        config=_base_config(deps),
    )

    ticket_id = result.get("ticket_id")
    partner_id = result.get("partner_id")

    try:
        assert result.get("error") is None
        assert ticket_id is not None
        assert isinstance(ticket_id, int)

        ticket = deps.odoo_service.get_ticket(ticket_id)
        assert ticket.get("name") == "Error en CRM"
    finally:
        _cleanup(deps, ticket_id, partner_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_email_normaliza_titulo_y_descripcion():
    graph = build_ticket_graph()
    deps = _build_deps('{"title": "Fallo en envío de correos", "description": "El envío automático de correos no funciona desde esta mañana.", "customer_name": "Beta SL", "customer_email": "soporte@beta.com"}')

    result = await graph.ainvoke(
        {
            "email_subject": "Problema con correos",
            "email_body": "Buenos días, en Beta SL no funciona el envío de correos automáticos.",
            "sender_email": "soporte@beta.com",
            "sender_name": "Beta SL",
        },
        config=_base_config(deps),
    )

    ticket_id = result.get("ticket_id")
    partner_id = result.get("partner_id")

    try:
        assert result.get("error") is None
        assert ticket_id is not None

        normalized = result["normalized_ticket"]
        assert normalized["title"] == "Fallo en envío de correos"
        assert normalized["customer_email"] == "soporte@beta.com"

        ticket = deps.odoo_service.get_ticket(ticket_id)
        assert ticket.get("name") == "Fallo en envío de correos"
    finally:
        _cleanup(deps, ticket_id, partner_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_email_sin_nombre_crea_ticket_sin_partner():
    graph = build_ticket_graph()
    deps = _build_deps('{"title": "Consulta general", "description": "Tengo una pregunta sobre el módulo de ventas.", "customer_name": null, "customer_email": null}')

    result = await graph.ainvoke(
        {
            "email_subject": "Consulta",
            "email_body": "Tengo una pregunta sobre el módulo de ventas.",
            "sender_email": "",
            "sender_name": None,
        },
        config=_base_config(deps),
    )

    ticket_id = result.get("ticket_id")

    try:
        assert result.get("error") is None
        assert ticket_id is not None
        assert result.get("partner_id") is None

        ticket = deps.odoo_service.get_ticket(ticket_id)
        assert ticket.get("name") == "Consulta general"
    finally:
        _cleanup(deps, ticket_id, None)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_json_invalido_devuelve_error():
    graph = build_ticket_graph()
    deps = _build_deps("esto no es json válido")

    result = await graph.ainvoke(
        {
            "email_subject": "Test",
            "email_body": "Cuerpo de prueba",
            "sender_email": "test@test.com",
            "sender_name": None,
        },
        config=_base_config(deps),
    )

    assert result.get("error") is not None
    assert "json" in result["error"].lower()
    assert result.get("ticket_id") is None
