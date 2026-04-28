from __future__ import annotations
"""Orquestación de mensajes posteriores en Discuss (La pagina principal de Odoo).

Este flujo se ejecuta cuando el usuario ya está hablando con Asistente Virtual
en un chat abierto desde un ticket. La decisión del router se hace sobre el
mensaje nuevo del usuario, no sobre el título histórico del ticket.
"""

from dataclasses import dataclass

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.dependencies import build_dependencies as build_budget_deps
from agents.budget_agent.graph import build_budget_graph
from agents.general_agent.service import GENERAL_AGENT_NAME, build_general_response
from orchestration.ticket_utils import build_budget_request_from_ticket
from routing.semantic_router import router


@dataclass(frozen=True)
class DiscussMessageOrchestrator:
    budget_deps_builder: callable

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

        # Para reutilizar budget_agent se reconstruye un ticket mínimo a partir del mensaje.
        ticket = {
            "id": payload.get("ticket_id"),
            "name": payload.get("ticket_title", ""),
            "description": payload.get("body", ""),
            "partner_name": payload.get("author_name", ""),
            "partner_email": payload.get("author_email", ""),
        }
        normalized_request = build_budget_request_from_ticket(ticket)
        if not normalized_request["requirements"]:
            return {
                "ok": False,
                "route_name": route_name,
                "agent_name": "budget_agent",
                "reply_text": "",
                "normalized_request": normalized_request,
                "quote_summary": {},
                "error": "El mensaje fue clasificado como budget, pero no se detectaron requisitos fiables.",
                "trace": trace + ["budget_request_incomplete"],
            }

        trace.append("budget_request_prepared")
        budget_deps: BudgetDependencies = self.budget_deps_builder(model=model)
        budget_result = await build_budget_graph().ainvoke(
            {"normalized_request": normalized_request},
            config={"configurable": {"deps": budget_deps, "thread_id": thread_id}},
        )

        if budget_result.get("error"):
            return {
                "ok": False,
                "route_name": route_name,
                "agent_name": "budget_agent",
                "reply_text": "",
                "normalized_request": normalized_request,
                "quote_summary": {},
                "error": budget_result["error"],
                "trace": trace + ["agent_failed:budget_agent"],
            }

        reply_text = ""
        messages = budget_result.get("messages", [])
        if messages:
            reply_text = getattr(messages[-1], "content", "") or ""

        return {
            "ok": True,
            "route_name": route_name,
            "agent_name": "budget_agent",
            "reply_text": reply_text,
            "normalized_request": normalized_request,
            "quote_summary": budget_result.get("quote_summary", {}),
            "trace": trace + ["agent_completed:budget_agent"],
        }


def build_discuss_routing_text(payload: dict) -> str:
    # El router solo necesita el mensaje actual y el autor; evita sesgos del ticket inicial.
    body = payload.get("body", "")
    author = payload.get("author_email", "")
    return f"Autor: {author}\nMensaje discuss: {body}".strip()


def build_discuss_message_orchestrator() -> DiscussMessageOrchestrator:
    return DiscussMessageOrchestrator(budget_deps_builder=build_budget_deps)
