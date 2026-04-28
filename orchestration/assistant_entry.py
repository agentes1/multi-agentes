from __future__ import annotations
"""Orquestación del flujo inicial desde ticket ya creado.

Este archivo se usa cuando Odoo crea un helpdesk.ticket manualmente.
Su responsabilidad es pequeña y muy concreta:
- convertir el ticket a texto enrutable
- decidir si entra por budget o fallback general
- invocar el agente adecuado
- devolver una respuesta lista para publicar en Discuss
"""

from dataclasses import dataclass

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.dependencies import build_dependencies as build_budget_deps
from agents.budget_agent.graph import build_budget_graph
from agents.general_agent.service import GENERAL_AGENT_NAME, build_general_response
from orchestration.ticket_utils import build_budget_request_from_ticket, build_ticket_text
from routing.semantic_router import router


@dataclass(frozen=True)
class TicketEntryOrchestrator:
    # Se inyecta el builder de dependencias para poder testear el flujo sin Odoo real.
    budget_deps_builder: callable

    async def handle_ticket_entry(
        self,
        ticket: dict,
        thread_id: str | None = None,
        model: str | None = None,
    ) -> dict:
        # El trace se devuelve a la API para poder depurar el recorrido del flujo.
        trace = ["ticket_received"]
        route_name = router(build_ticket_text(ticket)).name
        trace.append(f"route_decided:{route_name}")

        if route_name in {"discard", "issue"}:
            reply_text = build_general_response()
            return {
                "ok": True,
                "route_name": route_name,
                "agent_name": GENERAL_AGENT_NAME,
                "reply_text": reply_text,
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

        # Solo cuando la ruta es budget convertimos el ticket al formato del agente.
        normalized_request = build_budget_request_from_ticket(ticket)
        if not normalized_request["requirements"]:
            return {
                "ok": False,
                "route_name": route_name,
                "agent_name": "budget_agent",
                "reply_text": "",
                "normalized_request": normalized_request,
                "quote_summary": {},
                "error": "El ticket fue clasificado como budget, pero no se detectaron requisitos fiables.",
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


def build_ticket_entry_orchestrator() -> TicketEntryOrchestrator:
    return TicketEntryOrchestrator(budget_deps_builder=build_budget_deps)
