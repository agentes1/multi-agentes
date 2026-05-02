import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.tools import BudgetAgentTools
from agents.general_agent.service import GENERAL_AGENT_NAME, GENERAL_AGENT_RESPONSE
import api
from orchestration.assistant_discuss import DiscussMessageOrchestrator


class FakeBudgetOdooWrapper:
    def __init__(self):
        self.create_sale_order_called = False

    def list_catalog(self):
        return {
            "CRM": {"id": 11, "name": "CRM", "default_code": "CRM"},
            "AUTO": {
                "id": 22,
                "name": "Automatizacion Comercial",
                "default_code": "AUTO",
            },
        }

    def find_sale_order_by_client_ref(self, client_order_ref):
        return None

    def get_or_create_contact(self, company_name):
        return 501

    def create_sale_order(self, partner_id, client_order_ref=None):
        self.create_sale_order_called = True
        return 701

    def create_sale_order_line(self, order_id, product_id, quantity=1):
        return 1

    def get_sale_order(self, order_id):
        return {"id": order_id, "amount_untaxed": 3000.0, "amount_total": 3000.0}

    def get_sale_order_lines(self, order_id):
        return [
            {
                "name": "CRM",
                "product_uom_qty": 1,
                "price_unit": 1200.0,
                "price_subtotal": 1200.0,
                "default_code": "CRM",
            },
            {
                "name": "Automatizacion Comercial",
                "product_uom_qty": 1,
                "price_unit": 1800.0,
                "price_subtotal": 1800.0,
                "default_code": "AUTO",
            },
        ]


class FakeOdooMCPClient:
    def __init__(self, wrapper: FakeBudgetOdooWrapper):
        self.wrapper = wrapper

    def list_catalog(self):
        return self.wrapper.list_catalog()

    def get_or_create_contact(self, company_name: str):
        return self.wrapper.get_or_create_contact(company_name)

    def find_sale_order_by_client_ref(self, client_order_ref: str):
        return self.wrapper.find_sale_order_by_client_ref(client_order_ref)

    def create_sale_order(self, partner_id: int, client_order_ref: str | None = None):
        return self.wrapper.create_sale_order(partner_id, client_order_ref=client_order_ref)

    def create_sale_order_line(self, order_id: int, product_id: int, quantity: int = 1):
        return self.wrapper.create_sale_order_line(order_id, product_id, quantity=quantity)

    def get_sale_order(self, order_id: int):
        return self.wrapper.get_sale_order(order_id)

    def get_sale_order_lines(self, order_id: int):
        return self.wrapper.get_sale_order_lines(order_id)

    def get_product(self, product_id: int):
        return None

    def get_customer_profile(self, company_name: str):
        return {"segment": "pyme", "known_customer": True, "email": "alejandro@empresa.com"}

    def get_product_catalog_snapshot(self, product_ids: list[int]):
        return [
            {
                "id": 11,
                "name": "CRM",
                "default_code": "CRM",
                "price": 1200.0,
                "description": "Gestion comercial base.",
            },
            {
                "id": 22,
                "name": "Automatizacion Comercial",
                "default_code": "AUTO",
                "price": 1800.0,
                "description": "Automatizaciones para ventas.",
            },
        ]

    def find_related_products(self, product_ids: list[int], limit: int = 3):
        return [
            {
                "id": 31,
                "name": "Helpdesk y Soporte",
                "default_code": "HELP",
                "price": 950.0,
            }
        ][:limit]


class FakeBudgetLLM:
    async def ainvoke(self, messages):
        prompt = messages[-1].content
        if "Devuelve solo JSON" in prompt:
            if "product_ids" in prompt:
                return AIMessage(
                    content='{"product_ids": [11, 22], "unmatched_requirements": []}'
                )
            return AIMessage(
                content=(
                    '{"company_name": "Alejandro", '
                    '"project_summary": "Solicitud presupuesto CRM", '
                    '"requirements": ["crm", "automatizacion comercial"]}'
                )
            )
        return AIMessage(
            content=(
                "Hola Alejandro,\n\n"
                "He preparado un presupuesto inicial con los servicios detectados.\n"
                "Referencia del presupuesto: 701\n"
                "Importe total estimado: 3000.0 EUR\n"
                "Servicios incluidos: CRM, Automatizacion Comercial\n\n"
                f"Contexto usado: {prompt}"
            )
        )


def _build_budget_deps(wrapper: FakeBudgetOdooWrapper):
    def _builder(model: str | None = None) -> BudgetDependencies:
        return BudgetDependencies(
            llm=FakeBudgetLLM(),
            odoo_wrapper=wrapper,
            tools=BudgetAgentTools(mcp_client=FakeOdooMCPClient(wrapper)),
        )

    return _builder


@pytest.mark.asyncio
async def test_discuss_message_routes_budget_and_returns_reply() -> None:
    budget_wrapper = FakeBudgetOdooWrapper()
    orchestrator = DiscussMessageOrchestrator()

    result = await orchestrator.handle_discuss_message(
        payload={
            "ticket_id": 200,
            "ticket_title": "Solicitud inicial",
            "channel_id": 5,
            "channel_name": "Ticket 200 - Asistente Virtual",
            "message_id": 10,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "Hola, necesito presupuesto para CRM y automatizacion comercial en Odoo.",
        },
        thread_id="discuss-budget",
    )

    assert result["ok"] is True
    assert result["route_name"] == "budget"
    assert result["agent_name"] is None
    assert "Ready for next stage" in result["reply_text"]
    assert result["quote_summary"] == {}
    assert budget_wrapper.create_sale_order_called is False
    assert result["trace"] == [
        "discuss_message_received",
        "route_decided:budget",
        "budget_waiting_ready_state",
    ]


@pytest.mark.asyncio
async def test_discuss_message_routes_discard_and_returns_fixed_reply() -> None:
    budget_wrapper = FakeBudgetOdooWrapper()
    orchestrator = DiscussMessageOrchestrator()

    result = await orchestrator.handle_discuss_message(
        payload={
            "ticket_id": 201,
            "ticket_title": "Consulta",
            "channel_id": 6,
            "channel_name": "Ticket 201 - Asistente Virtual",
            "message_id": 11,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "Buenos dias, que tiempo hace hoy?",
        }
    )

    assert result["ok"] is True
    assert result["route_name"] == "discard"
    assert result["agent_name"] == GENERAL_AGENT_NAME
    assert result["reply_text"] == GENERAL_AGENT_RESPONSE
    assert budget_wrapper.create_sale_order_called is False
    assert result["trace"] == [
        "discuss_message_received",
        "route_decided:discard",
        "agent_completed:general_agent",
    ]


@pytest.mark.asyncio
async def test_discuss_message_ignores_budget_ticket_title_when_message_is_general() -> None:
    budget_wrapper = FakeBudgetOdooWrapper()
    orchestrator = DiscussMessageOrchestrator()

    result = await orchestrator.handle_discuss_message(
        payload={
            "ticket_id": 203,
            "ticket_title": "Necesito presupuesto para CRM",
            "channel_id": 8,
            "channel_name": "Ticket 203 - Asistente Virtual",
            "message_id": 13,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "Buenos dias, que tiempo hace hoy?",
        }
    )

    assert result["ok"] is True
    assert result["route_name"] == "discard"
    assert result["agent_name"] == GENERAL_AGENT_NAME
    assert result["reply_text"] == GENERAL_AGENT_RESPONSE
    assert budget_wrapper.create_sale_order_called is False


def test_assistant_discuss_message_api_returns_budget_reply(monkeypatch) -> None:
    budget_wrapper = FakeBudgetOdooWrapper()
    orchestrator = DiscussMessageOrchestrator()
    monkeypatch.setattr(api, "build_discuss_message_orchestrator", lambda: orchestrator)

    client = TestClient(api.app)
    response = client.post(
        "/assistant/discuss-message",
        json={
            "ticket_id": 202,
            "ticket_title": "Solicitud inicial",
            "channel_id": 7,
            "channel_name": "Ticket 202 - Asistente Virtual",
            "message_id": 12,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "Necesito presupuesto para CRM.",
            "thread_id": "discuss-api",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["route_name"] == "budget"
    assert payload["agent_name"] is None
    assert "Ready for next stage" in payload["reply_text"]
