from __future__ import annotations
"""Orquestación del flujo inicial desde ticket ya creado.

Este archivo se usa cuando Odoo crea un helpdesk.ticket manualmente.
Su responsabilidad es pequeña y muy concreta:
- convertir el ticket a texto enrutable
- decidir si se responde con fallback general o se espera a Ready for next stage
- devolver una respuesta lista para publicar en Discuss
"""

from agents.general_agent.service import GENERAL_AGENT_NAME, build_general_response
from orchestration.ticket_utils import build_ticket_text
from routing.semantic_router import router


class TicketEntryOrchestrator:
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
            reply_text = await build_general_response(
                text=build_ticket_text(ticket),
                model=model,
            )
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

        return {
            "ok": True,
            "route_name": route_name,
            "agent_name": None,
            "reply_text": (
                "He detectado que este ticket puede requerir presupuesto. "
                "Cuando lo marques como Ready for next stage crearé el presupuesto."
            ),
            "normalized_request": {},
            "quote_summary": {},
            "trace": trace + ["budget_waiting_ready_state"],
        }


def build_ticket_entry_orchestrator() -> TicketEntryOrchestrator:
    return TicketEntryOrchestrator()
