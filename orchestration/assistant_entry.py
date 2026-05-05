from __future__ import annotations

from agents.general_agent.service import GENERAL_AGENT_NAME
from agents.sales_agent.service import SALES_AGENT_NAME, build_sales_entry_reply
from orchestration.ticket_utils import build_ticket_text
from routing.semantic_router import router


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
        if route == "discard":
            return entry_response(route, GENERAL_AGENT_NAME, general_reply(), trace + [f"agent_completed:{GENERAL_AGENT_NAME}"])
        return entry_response(route, None, "", trace + ["no_agent_selected"])


def entry_response(route: str, agent: str | None, reply: str, trace: list[str]) -> dict:
    """Devuelve el formato estable de la API."""
    return {"ok": True, "route_name": route, "agent_name": agent, "reply_text": reply, "normalized_request": {}, "quote_summary": {}, "trace": trace}


def budget_reply() -> str:
    """Mensaje inicial para presupuestos."""
    return "He detectado una solicitud de presupuesto. Te ayudaré a concretarla y, cuando confirmes, la marcaré como 'Ready for next stage' para generar el presupuesto."


def general_reply() -> str:
    """Mensaje neutro si no hay ruta clara."""
    return "He recibido tu solicitud. Cuéntame si necesitas soporte, ventas o presupuesto para orientarte mejor."


def build_ticket_entry_orchestrator() -> TicketEntryOrchestrator:
    """Crea el orquestador de entrada."""
    return TicketEntryOrchestrator()