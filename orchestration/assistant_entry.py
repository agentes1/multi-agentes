from __future__ import annotations

from agents.general_agent.service import GENERAL_AGENT_NAME, build_general_response
from orchestration.ticket_utils import build_ticket_text
from routing.semantic_router import router


class TicketEntryOrchestrator:
    """Orquesta la entrada inicial desde un ticket manual de Odoo."""

    async def handle_ticket_entry(self, ticket: dict, thread_id: str | None = None, model: str | None = None) -> dict:
        """Decide si responder ahora o esperar a que el ticket avance de estado."""
        trace = ["ticket_received"]
        route_name = router(build_ticket_text(ticket)).name
        trace.append(f"route_decided:{route_name}")

        if route_name in {"discard", "issue"}:
            return build_ticket_entry_response(route_name, GENERAL_AGENT_NAME, build_general_response(), trace + [f"agent_completed:{GENERAL_AGENT_NAME}"])

        if route_name == "budget":
            reply = "He detectado que este ticket puede requerir presupuesto. Cuando lo marques como Ready for next stage crearé el presupuesto."
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


def build_ticket_entry_orchestrator() -> TicketEntryOrchestrator:
    """Crea el orquestador de entrada por ticket."""
    return TicketEntryOrchestrator()