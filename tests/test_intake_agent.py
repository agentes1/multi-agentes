import uuid

import pytest

from agents.intake_agent.dependencies import IntakeDependencies
from agents.intake_agent.graph import build_intake_graph
from odoo.api_wrapper import OdooAPIWrapper
from shared.config import ODOO_DB, ODOO_PASSWORD, ODOO_BASE_URL, ODOO_USERNAME


class MockLLMResponse:
    def __init__(self, content: str):
        self._content = content

    async def ainvoke(self, messages):
        class Response:
            content = self._content

        return Response()


def _build_deps(mock_json: str) -> IntakeDependencies:
    return IntakeDependencies(
        llm=MockLLMResponse(mock_json),
        odoo_service=OdooAPIWrapper(
            url=ODOO_BASE_URL,
            username=ODOO_USERNAME,
            password=ODOO_PASSWORD,
            db=ODOO_DB,
        ),
    )


def _base_config(deps: IntakeDependencies) -> dict:
    return {
        "configurable": {
            "deps": deps,
            "thread_id": f"test-intake-agent-{uuid.uuid4()}",
        }
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_email_crea_ticket_issue_real_en_odoo():
    graph = build_intake_graph()
    deps = _build_deps(
        """{
            "company_name": "Acme SL",
            "project_summary": "Error al crear oportunidades en Odoo CRM",
            "requirements": ["crm", "odoo"],
            "urgency": "alta",
            "ticket_type": "issue",
            "missing_information": ["Adjuntar captura del error"]
        }"""
    )

    result = await graph.ainvoke(
        {
            "source_input": {
                "channel": "email",
                "from": "cliente@acme.com",
                "subject": "Incidencia con CRM",
                "body": (
                    "Hola, somos Acme SL. "
                    "Tenemos un error al crear oportunidades en Odoo CRM "
                    "y necesitamos ayuda urgente."
                ),
            }
        },
        config=_base_config(deps),
    )

    ticket_id = result.get("ticket_id")

    try:
        assert result["error"] is None
        assert ticket_id is not None
        assert isinstance(ticket_id, int)

        # salida estructurada del agente
        assert result["ticket_type"] == "issue"
        assert result["normalized_request"]["company_name"] == "Acme SL"
        assert result["normalized_request"]["project_summary"] == "Error al crear oportunidades en Odoo CRM"
        assert result["normalized_request"]["requirements"] == ["crm", "odoo"]
        assert result["normalized_request"]["urgency"] == "alta"
        assert result["normalized_request"]["missing_information"] == ["Adjuntar captura del error"]

        # payload ya preparado para Odoo
        payload = result["ticket_payload"]
        assert payload["team_name"] == "Soporte cliente"
        assert payload["type_name"] == "Soporte"
        assert payload["category_name"] == "Problema"
        assert payload["priority"] == "2"
        assert "Faltan datos" in payload["tag_names"]
        assert "Urgente" in payload["tag_names"]

        # comprobación real en Odoo
        ticket = deps.odoo_service.get_helpdesk_ticket(ticket_id)
        assert ticket is not None
        assert ticket["id"] == ticket_id
        assert ticket["name"] == "Error al crear oportunidades en Odoo CRM"
        assert ticket["team_id"][0] == deps.odoo_service.get_team_id_by_name("Soporte cliente")

    finally:
        if ticket_id:
            print("fin")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_email_normaliza_urgency_y_ticket_type_y_crea_ticket():
    graph = build_intake_graph()
    deps = _build_deps(
        """{
            "company_name": "Beta SL",
            "project_summary": "No funciona el envío de correos automáticos",
            "requirements": ["correo automático", "odoo"],
            "urgency": "urgente",
            "ticket_type": "incidencia",
            "missing_information": []
        }"""
    )

    result = await graph.ainvoke(
        {
            "source_input": {
                "channel": "email",
                "from": "soporte@beta.com",
                "subject": "Problema con correos",
                "body": (
                    "Buenos días, en Beta SL no funciona el envío de correos automáticos."
                ),
            }
        },
        config=_base_config(deps),
    )

    ticket_id = result.get("ticket_id")

    try:
        assert result["error"] is None
        assert ticket_id is not None

        # normalizaciones
        assert result["normalized_request"]["urgency"] == "alta"
        assert result["normalized_request"]["ticket_type"] == "issue"
        assert result["ticket_type"] == "issue"

        payload = result["ticket_payload"]
        assert payload["team_name"] == "Soporte cliente"
        assert payload["priority"] == "2"
        assert "Urgente" in payload["tag_names"]

        ticket = deps.odoo_service.get_helpdesk_ticket(ticket_id)
        assert ticket is not None
        assert ticket["id"] == ticket_id
        assert ticket["name"] == "No funciona el envío de correos automáticos"

    finally:
        if ticket_id:
            print("fin")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_crea_ticket_real_en_odoo():
    graph = build_intake_graph()
    deps = _build_deps(
        """{
            "company_name": "Gamma Tech",
            "project_summary": "Fallo al visualizar dashboard de ventas",
            "requirements": ["dashboard", "ventas"],
            "urgency": "media",
            "ticket_type": "issue",
            "missing_information": []
        }"""
    )

    result = await graph.ainvoke(
        {
            "source_input": {
                "channel": "chat",
                "user_name": "Laura",
                "company_name": "Gamma Tech",
                "message": "No podemos visualizar el dashboard de ventas desde esta mañana.",
            }
        },
        config=_base_config(deps),
    )

    ticket_id = result.get("ticket_id")

    try:
        assert result["error"] is None
        assert ticket_id is not None

        assert result["ticket_type"] == "issue"
        assert result["normalized_request"]["company_name"] == "Gamma Tech"
        assert result["normalized_request"]["requirements"] == ["dashboard", "ventas"]
        assert result["normalized_request"]["urgency"] == "media"

        payload = result["ticket_payload"]
        assert payload["team_name"] == "Soporte cliente"
        assert payload["priority"] == "1"

        ticket = deps.odoo_service.get_helpdesk_ticket(ticket_id)
        assert ticket is not None
        assert ticket["id"] == ticket_id
        assert ticket["name"] == "Fallo al visualizar dashboard de ventas"

    finally:
        if ticket_id:
            print("fin")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_budget_crea_ticket_en_equipo_presupuestos():
    graph = build_intake_graph()
    deps = _build_deps(
        """{
            "company_name": "Delta Solutions",
            "project_summary": "Necesitamos propuesta para implantar CRM y automatización de emails",
            "requirements": ["crm", "automatización de emails"],
            "urgency": "baja",
            "ticket_type": "budget",
            "missing_information": []
        }"""
    )

    result = await graph.ainvoke(
        {
            "source_input": {
                "channel": "email",
                "from": "direccion@delta.com",
                "subject": "Solicitud de presupuesto",
                "body": (
                    "Queremos una propuesta para implantar CRM y automatizar emails."
                ),
            }
        },
        config=_base_config(deps),
    )

    ticket_id = result.get("ticket_id")

    try:
        assert result["error"] is None
        assert ticket_id is not None

        assert result["ticket_type"] == "budget"
        assert result["normalized_request"]["urgency"] == "baja"

        payload = result["ticket_payload"]
        assert payload["team_name"] == "Presupuestos"
        assert payload["type_name"] == "Presupuesto"
        assert payload["category_name"] == "Consulta presupuesto"
        assert payload["priority"] == "0"
        assert "Cliente nuevo" in payload["tag_names"]

        ticket = deps.odoo_service.get_helpdesk_ticket(ticket_id)
        assert ticket is not None
        assert ticket["id"] == ticket_id
        assert ticket["name"] == "Necesitamos propuesta para implantar CRM y automatización de emails"

    finally:
        if ticket_id:
            print("fin")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discard_crea_ticket_para_revision_manual():
    graph = build_intake_graph()
    deps = _build_deps(
        """{
            "company_name": "Empresa X",
            "project_summary": "Mensaje poco claro del cliente",
            "requirements": [],
            "urgency": "normal",
            "ticket_type": "spam",
            "missing_information": ["Aclarar la necesidad real del cliente"]
        }"""
    )

    result = await graph.ainvoke(
        {
            "source_input": {
                "channel": "email",
                "from": "contacto@empresax.com",
                "subject": "Consulta",
                "body": "Hola, queríamos hablar de algo del sistema, gracias.",
            }
        },
        config=_base_config(deps),
    )

    ticket_id = result.get("ticket_id")

    try:
        assert result["error"] is None
        assert ticket_id is not None

        # normalizaciones
        assert result["normalized_request"]["urgency"] == "media"
        assert result["normalized_request"]["ticket_type"] == "discard"
        assert result["ticket_type"] == "discard"

        payload = result["ticket_payload"]
        assert payload["team_name"] == "Soporte cliente"
        assert payload["type_name"] == "Soporte"
        assert payload["category_name"] == "Interno"
        assert payload["priority"] == "1"
        assert "Pendiente validación" in payload["tag_names"]
        assert "Faltan datos" in payload["tag_names"]

        ticket = deps.odoo_service.get_helpdesk_ticket(ticket_id)
        assert ticket is not None
        assert ticket["id"] == ticket_id
        assert ticket["name"] == "Mensaje poco claro del cliente"

    finally:
        if ticket_id:
            print("fin")