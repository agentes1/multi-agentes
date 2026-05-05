from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from agents.sales_agent.dependencies import SalesDependencies, build_dependencies as build_sales_deps
from agents.sales_agent.graph import build_sales_graph
from agents.sales_agent.service import SALES_AGENT_NAME


@dataclass(frozen=True)
class SalesFromTicketOrchestrator:
    """Orquesta la creación de oportunidades CRM desde tickets."""

    sales_deps_builder: Callable[..., SalesDependencies] = build_sales_deps

    async def handle_sales_from_ticket(self, ticket: dict, thread_id: str | None = None, model: str | None = None) -> dict:
        """Ejecuta el agente sales y normaliza la respuesta."""
        trace = ["sales_ticket_received"]
        result = await build_sales_graph().ainvoke(
            {"ticket": ticket},
            config={"configurable": {"deps": self.sales_deps_builder(model=model), "thread_id": thread_id}},
        )
        return sales_response(result, ok=not result.get("error"), trace=trace)


def sales_response(result: dict, ok: bool, trace: list[str]) -> dict:
    """Devuelve una respuesta estable para la API."""
    messages = result.get("messages") or []
    reply = getattr(messages[-1], "content", "") if messages and ok else ""
    status = "agent_completed:sales_agent" if ok else "agent_failed:sales_agent"
    return {
        "ok": ok,
        "agent_name": SALES_AGENT_NAME,
        "reply_text": reply,
        "crm_lead_id": result.get("crm_lead_id"),
        "crm_summary": result.get("crm_summary") or {},
        "error": None if ok else result.get("error"),
        "trace": trace + [status],
    }


def build_sales_from_ticket_orchestrator() -> SalesFromTicketOrchestrator:
    """Crea el orquestador sales."""
    return SalesFromTicketOrchestrator()