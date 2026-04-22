import pytest
from fastapi.testclient import TestClient

from agents.budget_agent.dependencies import BudgetDependencies
import api
from webhooks import TicketWebhookOrchestrator, extract_budget_requirements


class DummyOdooService:
    def __init__(self, ticket: dict):
        self._ticket = ticket
        self.channels = []
        self.messages = []

    def get_helpdesk_ticket(self, ticket_id: int):
        if self._ticket.get("id") == ticket_id:
            return self._ticket
        return None

    def get_or_create_discuss_bot_user(self, login='assistant.bot', name='Assistant Chatbot'):
        return {"id": 900, "login": login, "partner_id": [901, name], "name": name}

    def get_partner_by_email(self, email):
        if email:
            return {"id": 902, "email": email, "name": "Cliente"}
        return None

    def create_contact(self, data):
        return 903

    def open_direct_chat(self, partner_ids, channel_name):
        channel = {"id": 700, "name": channel_name, "partner_ids": partner_ids}
        self.channels.append(channel)
        return channel

    def post_message_to_channel(self, channel_id, body, author_id=None):
        self.messages.append(
            {"id": 800 + len(self.messages), "channel_id": channel_id, "body": body, "author_id": author_id}
        )
        return self.messages[-1]["id"]


class FakeBudgetOdooWrapper:
    def __init__(self):
        self.created_lines = []
        self.create_sale_order_called = False

    def find_products_by_text(self, text, limit=5):
        catalog = {
            "crm": {"id": 11, "name": "CRM", "default_code": "CRM"},
            "automatizacion comercial": {
                "id": 22,
                "name": "Automatizacion Comercial",
                "default_code": "AUTO",
            },
        }
        normalized = str(text).lower().strip()
        return [catalog[normalized]] if normalized in catalog else []

    def get_or_create_contact(self, company_name):
        return 501

    def create_sale_order(self, partner_id):
        self.create_sale_order_called = True
        return 701

    def create_sale_order_line(self, order_id, product_id, quantity=1):
        self.created_lines.append(
            {"order_id": order_id, "product_id": product_id, "quantity": quantity}
        )
        return len(self.created_lines)

    def get_sale_order(self, order_id):
        return {"id": order_id, "amount_untaxed": 3000.0, "amount_total": 3000.0}


def _build_odoo_service(ticket: dict):
    service = DummyOdooService(ticket)

    def _builder(model: str | None = None) -> DummyOdooService:
        return service
    return _builder


def _build_budget_deps(wrapper: FakeBudgetOdooWrapper):
    def _builder(model: str | None = None) -> BudgetDependencies:
        return BudgetDependencies(odoo_wrapper=wrapper)

    return _builder


@pytest.mark.asyncio
async def test_ticket_created_webhook_fetches_ticket_routes_budget_and_returns_agent_answer() -> None:
    ticket = {
        "id": 123,
        "name": "Solicitud presupuesto CRM",
        "description": (
            "Hola, queremos una propuesta para implantar CRM "
            "y automatizacion comercial en Odoo."
        ),
        "partner_email": "cliente@acme.com",
    }
    budget_wrapper = FakeBudgetOdooWrapper()

    orchestrator = TicketWebhookOrchestrator(
        odoo_service_builder=_build_odoo_service(ticket),
        budget_deps_builder=_build_budget_deps(budget_wrapper),
    )

    result = await orchestrator.handle_ticket_created(
        ticket_id=123,
        thread_id="webhook-test-thread",
    )

    assert result["ok"] is True
    assert result["stage"] == "budget"
    assert result["route_name"] == "budget"
    assert result["agent_name"] == "budget_agent"
    assert result["ticket"]["id"] == 123
    assert result["normalized_request"]["company_name"] == "cliente"
    assert result["quote_summary"]["sale_order_id"] == 701
    assert result["quote_summary"]["company_name"] == "cliente"
    assert "Presupuesto creado en Odoo para cliente" in result["assistant_reply"]
    assert result["chat_channel"]["id"] == 700
    assert result["chat_message_id"] == 800
    assert budget_wrapper.create_sale_order_called is True
    assert result["trace"] == [
        "webhook_received:123",
        "fetch_ticket:123",
        "ticket_loaded",
        "route_decided:budget",
        "chat_ready:700",
        "budget_request_prepared",
        "dispatch_agent:budget_agent",
        "agent_response_ready",
        "message_sent_to_chat",
        "agent_completed:budget_agent",
    ]


@pytest.mark.asyncio
async def test_ticket_created_webhook_does_not_call_budget_agent_for_non_budget_route() -> None:
    ticket = {
        "id": 456,
        "name": "Incidencia CRM",
        "description": "Tenemos un error al crear oportunidades y necesitamos soporte.",
        "partner_email": "cliente@acme.com",
    }
    budget_wrapper = FakeBudgetOdooWrapper()

    orchestrator = TicketWebhookOrchestrator(
        odoo_service_builder=_build_odoo_service(ticket),
        budget_deps_builder=_build_budget_deps(budget_wrapper),
    )

    result = await orchestrator.handle_ticket_created(ticket_id=456)

    assert result["ok"] is True
    assert result["stage"] == "routing"
    assert result["route_name"] == "issue"
    assert result["agent_name"] is None
    assert result["assistant_reply"] == ""
    assert result["quote_summary"] == {}
    assert result["chat_channel"]["id"] == 700
    assert result["chat_message_id"] is None
    assert budget_wrapper.create_sale_order_called is False
    assert result["trace"] == [
        "webhook_received:456",
        "fetch_ticket:456",
        "ticket_loaded",
        "route_decided:issue",
        "chat_ready:700",
        "no_agent_dispatched",
    ]


def test_webhook_api_end_to_end_returns_trace(monkeypatch) -> None:
    ticket = {
        "id": 321,
        "name": "Solicitud presupuesto CRM",
        "description": (
            "Hola, queremos una propuesta para implantar CRM "
            "y automatizacion comercial en Odoo."
        ),
        "partner_email": "cliente@acme.com",
    }
    budget_wrapper = FakeBudgetOdooWrapper()
    orchestrator = TicketWebhookOrchestrator(
        odoo_service_builder=_build_odoo_service(ticket),
        budget_deps_builder=_build_budget_deps(budget_wrapper),
    )

    monkeypatch.setattr(api, "build_ticket_webhook_orchestrator", lambda: orchestrator)

    client = TestClient(api.app)
    response = client.post(
        "/webhooks/odoo/tickets",
        json={"ticket_id": 321, "thread_id": "api-e2e"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["route_name"] == "budget"
    assert payload["agent_name"] == "budget_agent"
    assert payload["quote_summary"]["sale_order_id"] == 701
    assert payload["chat_channel"]["id"] == 700
    assert payload["chat_message_id"] == 800
    assert payload["trace"] == [
        "webhook_received:321",
        "fetch_ticket:321",
        "ticket_loaded",
        "route_decided:budget",
        "chat_ready:700",
        "budget_request_prepared",
        "dispatch_agent:budget_agent",
        "agent_response_ready",
        "message_sent_to_chat",
        "agent_completed:budget_agent",
    ]


def test_extract_budget_requirements_only_returns_detected_terms() -> None:
    requirements = extract_budget_requirements(
        "queremos implantar crm y automatizacion comercial en odoo"
    )
    assert requirements == ["automatizacion comercial", "crm"]
