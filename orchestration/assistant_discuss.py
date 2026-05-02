from __future__ import annotations
"""Orquestación de mensajes posteriores en Discuss (La pagina principal de Odoo).

Este flujo se ejecuta cuando el usuario ya está hablando con Asistente Virtual
en un chat abierto desde un ticket. La decisión del router se hace sobre el
mensaje nuevo del usuario, no sobre el título histórico del ticket.
"""

from agents.general_agent.service import GENERAL_AGENT_NAME, build_general_response
from routing.semantic_router import router


class DiscussMessageOrchestrator:
    async def handle_discuss_message(
        self,
        payload: dict,
        thread_id: str | None = None,
        model: str | None = None,
    ) -> dict:
        # El flujo es equivalente al de ticket-entry, pero la entrada es un mensaje de chat.
        trace = ["discuss_message_received"]
        text = build_discuss_routing_text(payload)
        route_name = router(text).name
        trace.append(f"route_decided:{route_name}")

        if route_name in {"discard", "issue"}:
            return {
                "ok": True,
                "route_name": route_name,
                "agent_name": GENERAL_AGENT_NAME,
                "reply_text": build_general_response(),
                "normalized_request": {},
                "quote_summary": {},
                "trace": trace + [f"agent_completed:{GENERAL_AGENT_NAME}"],
            }

        if route_name != "budget":
            return {
                "ok": True,
                "route_name": route_name,
                "agent_name": None,
                "reply_text": "",
                "normalized_request": {},
                "quote_summary": {},
                "trace": trace + ["no_agent_selected"],
            }

        return {
            "ok": True,
            "route_name": route_name,
            "agent_name": None,
            "reply_text": (
                "He detectado que este mensaje puede requerir presupuesto. "
                "Crearé el presupuesto cuando el ticket esté marcado como Ready for next stage."
            ),
            "normalized_request": {},
            "quote_summary": {},
            "trace": trace + ["budget_waiting_ready_state"],
        }


def build_discuss_routing_text(payload: dict) -> str:
    # El router solo necesita el mensaje actual y el autor; evita sesgos del ticket inicial.
    body = payload.get("body", "")
    author = payload.get("author_email", "")
    return f"Autor: {author}\nMensaje discuss: {body}".strip()


def build_discuss_message_orchestrator() -> DiscussMessageOrchestrator:
    return DiscussMessageOrchestrator()
