from __future__ import annotations

from agents.general_agent.service import GENERAL_AGENT_NAME
from agents.rag_agent.graph import build_rag_graph
from agents.rag_agent.dependencies import build_dependencies
from agents.sales_agent.service import SALES_AGENT_NAME, build_sales_entry_reply
from orchestration.ticket_utils import build_ticket_text
from routing.semantic_router import router

RAG_AGENT_NAME = "rag_agent"


class TicketEntryOrchestrator:
    """Orquesta la primera respuesta de un ticket manual."""

    async def handle_ticket_entry(self, ticket: dict, thread_id: str | None = None, model: str | None = None) -> dict:
        """Detecta ruta y responde sin crear aún registros de negocio."""
        trace = ["ticket_received"]
        route = router(build_ticket_text(ticket)).name
        trace.append(f"route_decided:{route}")

        if route == "sales":
            return entry_response(route, SALES_AGENT_NAME, build_sales_entry_reply(ticket), trace + [f"agent_completed:{SALES_AGENT_NAME}"])
        if route == "budget":
            return entry_response(route, None, budget_reply(), trace + ["budget_waiting_ready_state"])
        if route == "rag":
            reply = await run_rag_agent(build_ticket_text(ticket))
            return entry_response(route, RAG_AGENT_NAME, reply, trace + [f"agent_completed:{RAG_AGENT_NAME}"])
        if route == "discard":
            return entry_response(route, GENERAL_AGENT_NAME, general_reply(), trace + [f"agent_completed:{GENERAL_AGENT_NAME}"])
        return entry_response(route, None, "", trace + ["no_agent_selected"])


async def run_rag_agent(input_text: str) -> str:
    """Ejecuta el agente RAG y devuelve la respuesta."""
    try:
        graph = build_rag_graph()
        deps = build_dependencies()
        result = await graph.ainvoke(
            {"input_text": input_text},
            config={"configurable": {"deps": deps}},
        )
        return result.get("reply_text") or general_reply()
    except Exception:
        return general_reply()


def entry_response(route: str, agent: str | None, reply: str, trace: list[str]) -> dict:
    """Devuelve el formato estable de la API."""
    return {"ok": True, "route_name": route, "agent_name": agent, "reply_text": reply, "normalized_request": {}, "quote_summary": {}, "trace": trace}


def budget_reply() -> str:
    return "He detectado una solicitud de presupuesto. Te ayudaré a concretarla y, cuando confirmes, la marcaré como 'Ready for next stage' para generar el presupuesto."


def general_reply() -> str:
    return "He recibido tu solicitud. Cuéntame si necesitas soporte, ventas o presupuesto para orientarte mejor."


def build_ticket_entry_orchestrator() -> TicketEntryOrchestrator:
    return TicketEntryOrchestrator()