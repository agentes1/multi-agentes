import pytest
from fastapi.testclient import TestClient

from agents.assistant_chat_agent.service import ASSISTANT_CHAT_AGENT_NAME
from agents.sales_agent.service import SALES_AGENT_NAME
import api
from orchestration.assistant_discuss import DiscussMessageOrchestrator


def _build_orchestrator() -> DiscussMessageOrchestrator:
    return DiscussMessageOrchestrator()


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
    assert "Si quieres que siga adelante" in result["reply_text"]
    assert "<div" not in result["reply_text"]
    assert result["quote_summary"] == {}
    assert result["trace"] == [
        "discuss_message_received",
        "route_decided:budget",
        "response_built:discuss_orchestrator",
    ]
    assert result["actions"] == []


@pytest.mark.asyncio
async def test_discuss_message_routes_sales_and_returns_sales_reply() -> None:
    orchestrator = _build_orchestrator()

    result = await orchestrator.handle_discuss_message(
        payload={
            "ticket_id": 207,
            "ticket_title": "Pipeline comercial",
            "ticket_description": "Queremos ordenar oportunidades y seguimiento comercial.",
            "channel_id": 12,
            "channel_name": "Ticket 207 - Asistente Virtual",
            "message_id": 17,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "Queremos mejorar el pipeline y el seguimiento de leads.",
        }
    )

    assert result["ok"] is True
    assert result["route_name"] == "sales"
    assert result["agent_name"] == SALES_AGENT_NAME
    assert "objetivo comercial" in result["reply_text"] or "conversación comercial" in result["reply_text"]
    assert result["actions"] == []


@pytest.mark.asyncio
async def test_discuss_message_promotes_discard_to_sales_using_ticket_context() -> None:
    orchestrator = _build_orchestrator()

    result = await orchestrator.handle_discuss_message(
        payload={
            "ticket_id": 209,
            "ticket_title": "Pipeline comercial",
            "ticket_description": "Queremos mejorar oportunidades, leads y seguimiento comercial.",
            "channel_id": 14,
            "channel_name": "Ticket 209 - Asistente Virtual",
            "message_id": 19,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "de acuerdo",
        }
    )

    assert result["ok"] is True
    assert result["route_name"] == "sales"
    assert "context_route_promoted:sales" in result["trace"]


@pytest.mark.asyncio
async def test_discuss_message_marks_sales_ticket_ready_when_user_confirms_creation() -> None:
    orchestrator = _build_orchestrator()

    result = await orchestrator.handle_discuss_message(
        payload={
            "ticket_id": 208,
            "ticket_title": "Pipeline comercial",
            "ticket_description": "Queremos organizar oportunidades y seguimiento comercial.",
            "channel_id": 13,
            "channel_name": "Ticket 208 - Asistente Virtual",
            "message_id": 18,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "adelante",
            "recent_messages": [
                {
                    "author_name": "Asistente Virtual",
                    "body": "Cuando lo veas correcto, dime sí o adelante y lo marcaré como Ready for next stage para crear la oportunidad comercial en CRM.",
                }
            ],
        }
    )

    assert result["ok"] is True
    assert result["route_name"] == "sales"
    assert result["reply_text"] == "Perfecto, marco el ticket como listo para la siguiente fase para crear la oportunidad comercial en CRM."
    assert result["actions"] == [{"type": "mark_ticket_ready", "ticket_id": 208}]
    assert "sales_creation_confirmed" in result["trace"]


@pytest.mark.asyncio
async def test_discuss_message_marks_sales_ticket_ready_when_prompt_uses_quotes() -> None:
    orchestrator = _build_orchestrator()

    result = await orchestrator.handle_discuss_message(
        payload={
            "ticket_id": 210,
            "ticket_title": "Mejora del pipeline comercial",
            "ticket_description": "Queremos organizar oportunidades, leads y seguimiento comercial.",
            "channel_id": 15,
            "channel_name": "Ticket 210 - Asistente Virtual",
            "message_id": 20,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "adelante",
            "recent_messages": [
                {
                    "author_name": "Asistente Virtual",
                    "body": (
                        "He entendido que se trata de una conversación comercial. "
                        "Cuando lo veas correcto, dime 'sí' o 'adelante' y lo marcaré como "
                        "'Ready for next stage' para crear la oportunidad comercial en CRM."
                    ),
                }
            ],
        }
    )

    assert result["ok"] is True
    assert result["route_name"] == "sales"
    assert result["reply_text"] == "Perfecto, marco el ticket como listo para la siguiente fase para crear la oportunidad comercial en CRM."
    assert result["actions"] == [{"type": "mark_ticket_ready", "ticket_id": 210}]
    assert "sales_creation_confirmed" in result["trace"]


@pytest.mark.asyncio
async def test_discuss_message_routes_support_messages_to_discard() -> None:
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
    assert result["route_name"] == "discard"
    assert result["agent_name"] == ASSISTANT_CHAT_AGENT_NAME
    assert "Necesito un poco más de contexto" in result["reply_text"]


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
    assert "Hola. Para orientarte bien" in result["reply_text"]
    assert result["actions"] == []


@pytest.mark.asyncio
async def test_discuss_message_routes_short_reply_to_briefer_discard_prompt() -> None:
    orchestrator = _build_orchestrator()

    result = await orchestrator.handle_discuss_message(
        payload={
            "ticket_id": 206,
            "ticket_title": "Ayuda",
            "channel_id": 11,
            "channel_name": "Ticket 206 - Asistente Virtual",
            "message_id": 16,
            "author_name": "Alejandro",
            "author_email": "alejandro@empresa.com",
            "body": "mal",
        }
    )

    assert result["ok"] is True
    assert result["route_name"] == "discard"
    assert "Necesito un poco más de detalle" in result["reply_text"]


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
    assert result["reply_text"] == "Perfecto, marco el ticket como listo para la siguiente fase para generar el presupuesto."
    assert result["actions"] == [{"type": "mark_ticket_ready", "ticket_id": 204}]
    assert "budget_creation_confirmed" in result["trace"]
    assert "response_built:discuss_orchestrator" in result["trace"]


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
    assert "Si quieres que siga adelante" in payload["reply_text"]
    assert payload["actions"] == []
