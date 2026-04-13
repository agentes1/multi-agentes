# tests/test_intake_agent_integration.py
import pytest

from agents.intake_agent.dependencies import IntakeDependencies
from agents.intake_agent.graph import build_intake_graph
from odoo_integration.odoo_api_wrapper import OdooAPIWrapper
from shared.config import ODOO_DB, ODOO_PASSWORD, ODOO_BASE_URL, ODOO_USERNAME


class MockLLMEmailToIssue:
    async def ainvoke(self, messages):
        class Response:
            content = """{
                "company_name": "Acme SL",
                "project_summary": "Error al crear oportunidades en Odoo CRM",
                "requirements": ["crm", "odoo"],
                "urgency": "alta",
                "ticket_type": "issue",
                "missing_information": ["Adjuntar captura del error"]
            }"""

        return Response()


def _build_deps() -> IntakeDependencies:
    return IntakeDependencies(
        llm=MockLLMEmailToIssue(),
        odoo_service=OdooAPIWrapper(
            url=ODOO_BASE_URL,
            username=ODOO_USERNAME,
            password=ODOO_PASSWORD,
            db=ODOO_DB,
        ),
    )


def _base_config(deps: IntakeDependencies) -> dict:
    return {"configurable": {"deps": deps}}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_email_crea_ticket_real_en_odoo():
    graph = build_intake_graph()
    deps = _build_deps()

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

        assert result["ticket_type"] == "issue"
        assert result["normalized_request"]["company_name"] == "Acme SL"
        assert "crm" in result["normalized_request"]["requirements"]
        assert "odoo" in result["normalized_request"]["requirements"]

        payload = result["ticket_payload"]
        assert payload["team_name"] == "Soporte cliente"
        assert payload["type_name"] == "Soporte"
        assert payload["category_name"] == "Problema"
        assert payload["priority"] == "2"

        ticket = deps.odoo_service.get_helpdesk_ticket(ticket_id)
        assert ticket is not None
        assert ticket["id"] == ticket_id
        assert ticket["name"] == "Error al crear oportunidades en Odoo CRM"
        assert ticket["team_id"][0] == deps.odoo_service.get_team_id_by_name("Soporte cliente")

    finally:
        if ticket_id:
            print('fin')