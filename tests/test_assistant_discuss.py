import pytest
from fastapi.testclient import TestClient

from agents.assistant_chat_agent.service import ASSISTANT_CHAT_AGENT_NAME
import api
from orchestration.assistant_discuss import DiscussMessageOrchestrator


class FakeChatAgent:
    calls: list[dict] = []

    async def areply(self, payload: dict, route_name: str) -> str:
        self.calls.append({"payload": payload, "route_name": route_name})
        if route_name == "budget":
            return "Puedo ayudarte a concretar el presupuesto. Para avanzar, dime usuarios, modulos y plazo."
        if route_name == "budget_confirmed":
            return "Perfecto, marco el ticket como listo para que se genere el presupuesto."
        if route_name == "issue":
            return "Revisemos la incidencia. Indica el error exacto, pasos para reproducirlo y usuario afectado."
        return "Cuéntame un poco más para poder orientar el ticket correctamente."


def _build_orchestrator() -> DiscussMessageOrchestrator:
    FakeChatAgent.calls = []
    return DiscussMessageOrchestrator(chat_agent_builder=FakeChatAgent)


@pytest.mark.asyncio
async def test_discuss_message_routes_budget_and_uses_chat_agent() -> None:
    orchestrator = _build_orchestrator()

    result = await orchestrator.handle_discuss_message(
        payload={
            "ticket_id": 200,
            "ticket_title": "Solicitud inicial",
            "ticket_description": "Cliente interesado en CRM.",
            "ticket_partner_name": "ACME",
            "ticket_team": "Presupuestos",
            "ticket_stage": "New",
            "channel_id": 5,
            "channel_name": "Ticket 200 - Asistente Virtual",
            "message_id": 10,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "Hola, necesito presupuesto para CRM y automatizacion comercial en Odoo.",
            "recent_messages": [
                {"author_name": "Asistente Virtual", "body": "Hola, he recibido tu ticket."},
                {"author_name": "Alejandro", "body": "Necesito presupuesto para CRM."},
            ],
        },
        thread_id="discuss-budget",
    )

    assert result["ok"] is True
    assert result["route_name"] == "budget"
    assert result["agent_name"] == ASSISTANT_CHAT_AGENT_NAME
    assert "usuarios, modulos y plazo" in result["reply_text"]
    assert result["quote_summary"] == {}
    assert FakeChatAgent.calls[0]["route_name"] == "budget"
    assert FakeChatAgent.calls[0]["payload"]["ticket_team"] == "Presupuestos"
    assert FakeChatAgent.calls[0]["payload"]["recent_messages"][0]["author_name"] == "Asistente Virtual"
    assert result["trace"] == [
        "discuss_message_received",
        "route_decided:budget",
        "agent_completed:assistant_chat_agent",
    ]
    assert result["actions"] == []


@pytest.mark.asyncio
async def test_discuss_message_routes_issue_and_uses_chat_agent() -> None:
    orchestrator = _build_orchestrator()

    result = await orchestrator.handle_discuss_message(
        payload={
            "ticket_id": 201,
            "ticket_title": "Error en facturacion",
            "ticket_team": "Soporte cliente",
            "ticket_stage": "New",
            "channel_id": 6,
            "channel_name": "Ticket 201 - Asistente Virtual",
            "message_id": 11,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "Me aparece un error al guardar una factura.",
        }
    )

    assert result["ok"] is True
    assert result["route_name"] == "issue"
    assert result["agent_name"] == ASSISTANT_CHAT_AGENT_NAME
    assert "pasos para reproducirlo" in result["reply_text"]
    assert FakeChatAgent.calls[0]["route_name"] == "issue"


@pytest.mark.asyncio
async def test_discuss_message_routes_discard_but_still_uses_chat_agent() -> None:
    orchestrator = _build_orchestrator()

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
    assert result["agent_name"] == ASSISTANT_CHAT_AGENT_NAME
    assert "orientar el ticket" in result["reply_text"]
    assert FakeChatAgent.calls[0]["route_name"] == "discard"
    assert result["actions"] == []


@pytest.mark.asyncio
async def test_discuss_message_marks_budget_ticket_ready_when_user_confirms_creation() -> None:
    orchestrator = _build_orchestrator()

    result = await orchestrator.handle_discuss_message(
        payload={
            "ticket_id": 204,
            "ticket_title": "Presupuesto CRM",
            "ticket_description": "Cliente interesado en CRM.",
            "ticket_partner_name": "ACME",
            "ticket_team": "Presupuestos",
            "ticket_stage": "New",
            "channel_id": 9,
            "channel_name": "Ticket 204 - Asistente Virtual",
            "message_id": 14,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "Si.",
            "recent_messages": [
                {
                    "author_name": "Asistente Virtual",
                    "body": "Tengo los datos principales. Quieres que preparemos el presupuesto?",
                },
                {"author_name": "Alejandro", "body": "Si."},
            ],
        },
        thread_id="discuss-budget-confirmed",
    )

    assert result["ok"] is True
    assert result["route_name"] == "budget"
    assert result["reply_text"] == "Perfecto, marco el ticket como listo para que se genere el presupuesto."
    assert result["actions"] == [{"type": "mark_ticket_ready", "ticket_id": 204}]
    assert FakeChatAgent.calls[0]["route_name"] == "budget_confirmed"
    assert result["trace"] == [
        "discuss_message_received",
        "route_decided:discard",
        "budget_creation_confirmed",
        "agent_completed:assistant_chat_agent",
    ]


@pytest.mark.asyncio
async def test_discuss_message_marks_budget_ticket_ready_after_confirmation_prompt() -> None:
    orchestrator = _build_orchestrator()

    result = await orchestrator.handle_discuss_message(
        payload={
            "ticket_id": 205,
            "ticket_title": "Presupuesto!!!!!",
            "ticket_description": "Necesita un presupuesto CRM para mañana.",
            "ticket_partner_name": "ACME",
            "ticket_team": "Presupuestos",
            "ticket_stage": "New",
            "channel_id": 10,
            "channel_name": "Ticket 205 - Asistente Virtual",
            "message_id": 15,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "Sí",
            "recent_messages": [
                {
                    "author_name": "Asistente Virtual",
                    "body": (
                        "Entiendo que necesitas un presupuesto CRM para mañana. "
                        "¿Podrías confirmar si es correcto? Si es así, marcaré tu solicitud "
                        "como 'Ready for next stage' y crearé el presupuesto correspondiente."
                    ),
                },
                {"author_name": "Alejandro", "body": "Sí"},
            ],
        },
        thread_id="discuss-budget-confirmed",
    )

    assert result["ok"] is True
    assert result["route_name"] == "budget"
    assert result["actions"] == [{"type": "mark_ticket_ready", "ticket_id": 205}]
    assert FakeChatAgent.calls[0]["route_name"] == "budget_confirmed"
    assert "budget_creation_confirmed" in result["trace"]


def test_assistant_discuss_message_api_accepts_ticket_context_and_history(monkeypatch) -> None:
    orchestrator = _build_orchestrator()
    monkeypatch.setattr(api, "build_discuss_message_orchestrator", lambda: orchestrator)

    client = TestClient(api.app)
    response = client.post(
        "/assistant/discuss-message",
        json={
            "ticket_id": 202,
            "ticket_title": "Solicitud inicial",
            "ticket_description": "Necesita valorar CRM.",
            "ticket_partner_name": "ACME",
            "ticket_partner_email": "cliente@acme.com",
            "ticket_team": "Presupuestos",
            "ticket_category": "Consulta presupuesto",
            "ticket_type": "Presupuesto",
            "ticket_stage": "New",
            "channel_id": 7,
            "channel_name": "Ticket 202 - Asistente Virtual",
            "message_id": 12,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "Necesito presupuesto para CRM.",
            "recent_messages": [{"author_name": "Alejandro", "body": "Necesito presupuesto para CRM."}],
            "thread_id": "discuss-api",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["route_name"] == "budget"
    assert payload["agent_name"] == ASSISTANT_CHAT_AGENT_NAME
    assert "usuarios, modulos y plazo" in payload["reply_text"]
    assert payload["actions"] == []
    assert FakeChatAgent.calls[0]["payload"]["ticket_partner_name"] == "ACME"
