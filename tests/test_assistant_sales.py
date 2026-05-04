import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api
from orchestration.assistant_sales import SalesFromTicketOrchestrator


class FakeSalesLLM:
    async def ainvoke(self, messages):
        prompt = messages[-1].content
        if "Devuelve solo JSON válido" in prompt:
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "company_name": "ACME",
                        "sales_summary": "Mejorar pipeline y seguimiento comercial",
                        "commercial_goals": ["pipeline", "seguimiento de leads"],
                        "next_step": "Revisar alcance comercial",
                    },
                    ensure_ascii=False,
                )
            )
        return SimpleNamespace(
            content="He creado la oportunidad comercial en CRM y queda lista para seguimiento."
        )


class FakeSalesMCPClient:
    def __init__(self):
        self.created = False
        self.created_payload = None

    def find_crm_opportunity_by_source_ticket(self, ticket_id: int):
        return None

    def get_or_create_contact(self, company_name: str, email: str | None = None):
        return 901

    def get_customer_profile(self, company_name: str):
        return {
            "known_customer": True,
            "partner_id": 901,
            "name": company_name,
            "email": "ventas@acme.com",
            "segment": "standard",
        }

    def get_customer_history(self, partner_id: int, limit: int = 10):
        return {
            "orders": [{"id": 55, "name": "S00055"}],
            "tickets": [{"id": 77, "name": "Seguimiento CRM"}],
        }

    def create_crm_opportunity(
        self,
        title: str,
        description: str,
        partner_id: int | None = None,
        partner_name: str | None = None,
        partner_email: str | None = None,
        source_ticket_id: int | None = None,
        priority: str | None = None,
    ):
        self.created = True
        self.created_payload = {
            "title": title,
            "description": description,
            "partner_id": partner_id,
            "partner_name": partner_name,
            "partner_email": partner_email,
            "source_ticket_id": source_ticket_id,
            "priority": priority,
        }
        return 1201

    def get_crm_opportunity(self, opportunity_id: int):
        return {
            "id": opportunity_id,
            "name": "Oportunidad CRM",
            "type": "opportunity",
        }


def _build_fake_deps():
    return SimpleNamespace(llm=FakeSalesLLM(), odoo_mcp_client=FakeSalesMCPClient())


@pytest.mark.asyncio
async def test_sales_from_ticket_creates_crm_opportunity() -> None:
    fake_deps = _build_fake_deps()
    orchestrator = SalesFromTicketOrchestrator(sales_deps_builder=lambda model=None: fake_deps)

    result = await orchestrator.handle_sales_from_ticket(
        ticket={
            "id": 301,
            "name": "Pipeline comercial",
            "description": "Queremos mejorar el seguimiento de leads y oportunidades.",
            "partner_name": "ACME",
            "partner_email": "ventas@acme.com",
        }
    )

    assert result["ok"] is True
    assert result["agent_name"] == "sales_agent"
    assert result["crm_lead_id"] == 1201
    assert result["trace"] == [
        "sales_ticket_received",
        "agent_completed:sales_agent",
    ]
    assert fake_deps.odoo_mcp_client.created is True
    assert fake_deps.odoo_mcp_client.created_payload["source_ticket_id"] == 301
    assert fake_deps.odoo_mcp_client.created_payload["title"].startswith("ACME - ")
    assert fake_deps.odoo_mcp_client.created_payload["priority"] == "2"
    assert "Objetivos comerciales" in fake_deps.odoo_mcp_client.created_payload["description"]
    assert "Perfil cliente" in fake_deps.odoo_mcp_client.created_payload["description"]
    assert "Historial reciente" in fake_deps.odoo_mcp_client.created_payload["description"]


def test_sales_from_ticket_api_returns_created_opportunity(monkeypatch) -> None:
    fake_deps = _build_fake_deps()
    orchestrator = SalesFromTicketOrchestrator(sales_deps_builder=lambda model=None: fake_deps)
    monkeypatch.setattr(api, "build_sales_from_ticket_orchestrator", lambda: orchestrator)

    client = TestClient(api.app)
    response = client.post(
        "/assistant/sales-from-ticket",
        json={
            "ticket_id": 302,
            "title": "Pipeline comercial",
            "description": "Queremos mejorar oportunidades y seguimiento de leads.",
            "partner_name": "ACME",
            "partner_email": "ventas@acme.com",
            "thread_id": "sales-api",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["crm_lead_id"] == 1201
    assert payload["agent_name"] == "sales_agent"
