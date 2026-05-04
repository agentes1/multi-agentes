from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from agents.sales_agent.dependencies import SalesDependencies
from agents.sales_agent.dependencies import build_dependencies as build_sales_deps
from agents.sales_agent.graph import build_sales_graph
from agents.sales_agent.service import SALES_AGENT_NAME


@dataclass(frozen=True)
class SalesFromTicketOrchestrator:
    """Crea oportunidades de CRM a partir de tickets confirmados."""

    sales_deps_builder: Callable[..., SalesDependencies] = build_sales_deps

    async def handle_sales_from_ticket(self, ticket: dict, thread_id: str | None = None, model: str | None = None) -> dict:
        trace = ["sales_ticket_received"]
        deps = self.sales_deps_builder(model=model)

        result = await build_sales_graph().ainvoke(
            {"ticket": ticket},
            config={"configurable": {"deps": deps, "thread_id": thread_id}},
        )

        if result.get("error"):
            return {
                "ok": False,
                "agent_name": SALES_AGENT_NAME,
                "reply_text": "",
                "crm_lead_id": result.get("crm_lead_id"),
                "crm_summary": result.get("crm_summary") or {},
                "error": result.get("error"),
                "trace": trace + ["agent_failed:sales_agent"],
            }

        messages = result.get("messages") or []
        reply_text = getattr(messages[-1], "content", "") if messages else ""

        return {
            "ok": True,
            "agent_name": SALES_AGENT_NAME,
            "reply_text": reply_text,
            "crm_lead_id": result.get("crm_lead_id"),
            "crm_summary": result.get("crm_summary") or {},
            "error": None,
            "trace": trace + ["agent_completed:sales_agent"],
        }


def build_sales_from_ticket_orchestrator() -> SalesFromTicketOrchestrator:
    return SalesFromTicketOrchestrator()
