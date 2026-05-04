from __future__ import annotations

from agents.general_agent.service import GENERAL_AGENT_NAME
from agents.sales_agent.service import SALES_AGENT_NAME, build_sales_entry_reply
from orchestration.ticket_utils import build_ticket_text
from routing.semantic_router import router


class TicketEntryOrchestrator:
    """Orquesta la entrada inicial desde un ticket manual de Odoo."""

    async def handle_ticket_entry(self, ticket: dict, thread_id: str | None = None, model: str | None = None) -> dict:
        """Decide si responder ahora o esperar a que el ticket avance de estado."""
        trace = ["ticket_received"]
        route_name = router(build_ticket_text(ticket)).name
        trace.append(f"route_decided:{route_name}")

        if route_name == "discard":
            reply_text = _build_entry_reply(route_name)
            return build_ticket_entry_response(
                route_name,
                GENERAL_AGENT_NAME,
                reply_text,
                trace + [f"agent_completed:{GENERAL_AGENT_NAME}"],
            )

        if route_name == "sales":
            reply_text = build_sales_entry_reply(ticket)
            return build_ticket_entry_response(
                route_name,
                SALES_AGENT_NAME,
                reply_text,
                trace + [f"agent_completed:{SALES_AGENT_NAME}"],
            )

        if route_name == "budget":
            reply = (
                "He detectado que este ticket parece una solicitud de presupuesto. "
                "Voy a ayudarte por este chat a concretarlo y, cuando me confirmes que siga adelante, "
                "lo marcaré como 'Ready for next stage' para generar el presupuesto."
            )
            return build_ticket_entry_response(route_name, None, reply, trace + ["budget_waiting_ready_state"])

        return build_ticket_entry_response(route_name, None, "", trace + ["no_agent_selected"])


def build_ticket_entry_response(route_name: str, agent_name: str | None, reply_text: str, trace: list[str]) -> dict:
    """Construye una respuesta estable para la API."""
    return {
        "ok": True,
        "route_name": route_name,
        "agent_name": agent_name,
        "reply_text": reply_text,
        "normalized_request": {},
        "quote_summary": {},
        "trace": trace,
    }


def _build_entry_reply(route_name: str) -> str:
    return (
        "He recibido tu solicitud. Si necesitas soporte, indícame el problema concreto; "
        "si buscas un presupuesto, dime qué módulos, alcance o necesidades quieres valorar."
    )


def build_ticket_entry_orchestrator() -> TicketEntryOrchestrator:
    """Crea el orquestador de entrada por ticket."""
    return TicketEntryOrchestrator()
