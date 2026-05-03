from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.dependencies import build_dependencies as build_budget_deps
from agents.budget_agent.graph import build_budget_graph


@dataclass(frozen=True)
class BudgetFromTicketOrchestrator:
    budget_deps_builder: Callable

    async def handle_budget_from_ticket(
        self,
        ticket: dict,
        thread_id: str | None = None,
        model: str | None = None,
    ) -> dict:
        trace = ["budget_ticket_received"]
        budget_deps: BudgetDependencies = self.budget_deps_builder(model=model)
        result = await build_budget_graph().ainvoke(
            {"ticket": ticket},
            config={"configurable": {"deps": budget_deps, "thread_id": thread_id}},
        )

        if result.get("error"):
            return {
                "ok": False,
                "agent_name": "budget_agent",
                "reply_text": "",
                "sale_order_id": result.get("sale_order_id"),
                "normalized_request": result.get("normalized_request", {}) or {},
                "quote_summary": result.get("quote_summary", {}) or {},
                "error": result["error"],
                "trace": trace + ["agent_failed:budget_agent"],
            }

        messages = result.get("messages", [])
        reply_text = getattr(messages[-1], "content", "") if messages else ""
        quote_summary = result.get("quote_summary", {}) or {}
        return {
            "ok": True,
            "agent_name": "budget_agent",
            "reply_text": reply_text,
            "sale_order_id": result.get("sale_order_id") or quote_summary.get("sale_order_id"),
            "normalized_request": result.get("normalized_request", {}) or {},
            "quote_summary": quote_summary,
            "error": None,
            "trace": trace + ["agent_completed:budget_agent"],
        }


def build_budget_from_ticket_orchestrator() -> BudgetFromTicketOrchestrator:
    return BudgetFromTicketOrchestrator(budget_deps_builder=build_budget_deps)
