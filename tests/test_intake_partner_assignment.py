# tests/test_intake_partner_assignment.py

import json
import pytest
from langchain_core.messages import AIMessage

from agents.intake_agent.nodes import prepare_ticket_node, create_ticket_node


class FakeLLM:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content=self.responses.pop(0))


class FakeOdooMCPClient:
    def __init__(self, companies=None):
        self.companies = companies or []
        self.created_ticket_kwargs = None

    def find_company(self, name, exact=False, limit=20):
        return self.companies[:limit]

    def get_customer_history(self, company_id):
        return {"orders": [], "tickets": []}

    def find_helpdesk_team(self, name):
        return {"id": 10, "name": name}

    def find_ticket_type(self, name):
        return {"id": 20, "name": name}

    def find_ticket_category(self, name):
        return {"id": 30, "name": name}

    def find_ticket_tags(self, tag_names):
        return list(range(1, len(tag_names) + 1))

    def create_helpdesk_ticket(self, **kwargs):
        self.created_ticket_kwargs = kwargs
        return 999


class FakeDeps:
    def __init__(self, llm, odoo_mcp_client):
        self.llm = llm
        self.odoo_mcp_client = odoo_mcp_client


def make_config(deps):
    return {
        "configurable": {
            "deps": deps,
        }
    }


@pytest.mark.asyncio
async def test_ticket_uses_company_as_partner_when_company_matches():
    """
    Caso esperado:
    - El request trae una empresa detectada.
    - Odoo ya tiene una empresa parecida.
    - El LLM selecciona esa empresa.
    - El ticket se crea con partner_id igual al id de la empresa.
    """

    llm = FakeLLM([
        json.dumps({"company_id": 7}),
    ])

    odoo = FakeOdooMCPClient(
        companies=[
            {"id": 7, "name": "ACME S.L."},
            {"id": 8, "name": "Otra Empresa"},
        ]
    )

    deps = FakeDeps(llm=llm, odoo_mcp_client=odoo)

    state = {
        "normalized_request": {
            "company_name": "ACME",
            "project_summary": "Necesitan presupuesto de implantación",
            "requirements": ["Implantación de Odoo"],
            "urgency": "media",
            "ticket_type": "budget",
            "missing_information": [],
            "sender_name": "Juan Pérez",
            "sender_email": "juan@acme.com",
        },
        "ticket_type": "budget",
        "source_input": {
            "channel": "email",
        },
    }

    prepared = await prepare_ticket_node(state, make_config(deps))

    assert prepared["error"] is None
    assert prepared["ticket_payload"]["company_id"] == 7
    assert prepared["ticket_payload"]["company_name"] == "ACME S.L."
    assert "Cliente nuevo" not in prepared["ticket_payload"]["tag_names"]

    create_state = {
        **state,
        "ticket_payload": prepared["ticket_payload"],
    }

    created = await create_ticket_node(create_state, make_config(deps))

    assert created["error"] is None
    assert created["ticket_id"] == 999

    assert odoo.created_ticket_kwargs is not None
    assert odoo.created_ticket_kwargs["partner_id"] == 7
    assert odoo.created_ticket_kwargs["partner_name"] == "ACME S.L."
    assert odoo.created_ticket_kwargs["partner_email"] == "juan@acme.com"


@pytest.mark.asyncio
async def test_ticket_has_no_partner_and_cliente_nuevo_when_company_does_not_match():
    """
    Caso esperado:
    - El request trae una empresa detectada.
    - Odoo tiene empresas, pero el LLM no ve un match claro.
    - El ticket queda sin partner_id.
    - Se añade el tag Cliente nuevo.
    - Se añade una observación en warnings.
    """

    llm = FakeLLM([
        json.dumps({"company_id": None}),
    ])

    odoo = FakeOdooMCPClient(
        companies=[
            {"id": 7, "name": "ACME S.L."},
            {"id": 8, "name": "Otra Empresa"},
        ]
    )

    deps = FakeDeps(llm=llm, odoo_mcp_client=odoo)

    state = {
        "normalized_request": {
            "company_name": "Empresa Nueva",
            "project_summary": "Solicitan soporte inicial",
            "requirements": ["Revisar integración"],
            "urgency": "alta",
            "ticket_type": "issue",
            "missing_information": [],
            "sender_name": "Laura",
            "sender_email": "laura@empresanueva.com",
        },
        "ticket_type": "issue",
        "source_input": {
            "channel": "email",
        },
    }

    prepared = await prepare_ticket_node(state, make_config(deps))

    assert prepared["error"] is None
    assert prepared["ticket_payload"]["company_id"] is None
    assert prepared["ticket_payload"]["company_name"] is None
    assert "Cliente nuevo" in prepared["ticket_payload"]["tag_names"]
    assert "Urgente" in prepared["ticket_payload"]["tag_names"]

    create_state = {
        **state,
        "ticket_payload": prepared["ticket_payload"],
    }

    created = await create_ticket_node(create_state, make_config(deps))

    assert created["error"] is None
    assert created["ticket_id"] == 999

    assert odoo.created_ticket_kwargs is not None
    assert odoo.created_ticket_kwargs["partner_id"] is None

    assert created["warnings"] == ["Empresa 'Empresa Nueva' no asociada"]
