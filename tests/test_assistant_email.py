import pytest
from fastapi.testclient import TestClient

import api
from orchestration.assistant_email import IncomingEmailOrchestrator


class FakeIntakeGraph:
    async def ainvoke(self, state, config=None):
        source_input = state["source_input"]
        if "presupuesto" in source_input.get("subject", "").lower():
            return {
                "error": None,
                "ticket_id": 321,
                "ticket_type": "budget",
                "final_text": "Ticket creado correctamente en Odoo con id 321 y tipo budget.",
                "normalized_request": {
                    "company_name": "Acme",
                    "ticket_type": "budget",
                },
                "ticket_payload": {
                    "title": "Solicitud de presupuesto",
                    "team_name": "Presupuestos",
                },
                "warnings": [],
            }
        return {
            "error": "No se pudo procesar el correo",
            "ticket_id": None,
            "final_text": "Error: No se pudo procesar el correo",
            "normalized_request": {},
            "ticket_payload": {},
            "warnings": [],
        }


class FakeTicketEntryOrchestrator:
    async def handle_ticket_entry(self, ticket, thread_id=None, model=None):
        return {
            "ok": True,
            "route_name": "budget",
            "agent_name": "budget_agent",
            "reply_text": (
                f"He preparado una respuesta para el ticket {ticket['id']} "
                f"del cliente {ticket.get('partner_email', '')}."
            ),
            "quote_summary": {"sale_order_id": 701},
            "trace": ["ticket_received", "route_decided:budget", "agent_completed:budget_agent"],
        }


@pytest.mark.asyncio
async def test_incoming_email_orchestrator_runs_intake_graph(monkeypatch):
    monkeypatch.setattr("orchestration.assistant_email.build_intake_graph", lambda: FakeIntakeGraph())

    orchestrator = IncomingEmailOrchestrator(
        intake_deps_builder=lambda: object(),
        ticket_entry_orchestrator_builder=lambda: FakeTicketEntryOrchestrator(),
    )
    result = await orchestrator.handle_incoming_email(
        payload={
            "inbox_id": 7,
            "subject": "Solicitud de presupuesto",
            "email_from": "cliente@acme.com",
            "body": "Necesitamos CRM e implantacion de Odoo.",
        },
        thread_id="mail-test",
    )

    assert result["ok"] is True
    assert result["ticket_id"] == 321
    assert result["route_name"] == "budget"
    assert result["agent_name"] == "budget_agent"
    assert "cliente@acme.com" in result["reply_text"]
    assert result["normalized_request"]["ticket_type"] == "budget"
    assert result["ticket_payload"]["team_name"] == "Presupuestos"
    assert result["trace"] == [
        "incoming_email_received",
        "ticket_type_decided:budget",
        "ticket_created:321",
        "ticket_received",
        "route_decided:budget",
        "agent_completed:budget_agent",
    ]


def test_incoming_email_api_returns_ticket_created(monkeypatch):
    orchestrator = IncomingEmailOrchestrator(
        intake_deps_builder=lambda: object(),
        ticket_entry_orchestrator_builder=lambda: FakeTicketEntryOrchestrator(),
    )
    monkeypatch.setattr("orchestration.assistant_email.build_intake_graph", lambda: FakeIntakeGraph())
    monkeypatch.setattr(api, "build_incoming_email_orchestrator", lambda: orchestrator)

    client = TestClient(api.app)
    response = client.post(
        "/assistant/incoming-email",
        json={
            "inbox_id": 9,
            "subject": "Solicitud de presupuesto",
            "email_from": "cliente@acme.com",
            "body": "Necesitamos CRM e implantacion de Odoo.",
            "thread_id": "mail-api",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["ticket_id"] == 321
    assert payload["route_name"] == "budget"
    assert payload["agent_name"] == "budget_agent"
    assert payload["trace"] == [
        "incoming_email_received",
        "ticket_type_decided:budget",
        "ticket_created:321",
        "ticket_received",
        "route_decided:budget",
        "agent_completed:budget_agent",
    ]
