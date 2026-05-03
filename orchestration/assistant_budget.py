from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Callable

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.dependencies import build_dependencies as build_budget_deps
from agents.budget_agent.graph import build_budget_graph


@dataclass(frozen=True)
class BudgetFromTicketOrchestrator:
    """Orquesta la creación de presupuestos desde tickets ya validados."""

    budget_deps_builder: Callable[..., BudgetDependencies] = build_budget_deps

    async def handle_budget_from_ticket(self, ticket: dict, thread_id: str | None = None, model: str | None = None) -> dict:
        """Ejecuta el agente de presupuestos y normaliza su respuesta."""
        trace = ["budget_ticket_received"]
        deps = self.budget_deps_builder(model=model)

        result = await build_budget_graph().ainvoke(
            {"ticket": ticket},
            config={"configurable": {"deps": deps, "thread_id": thread_id}},
        )

        if result.get("error"):
            return build_budget_response(result, ok=False, trace=trace + ["agent_failed:budget_agent"])

        return build_budget_response(result, ok=True, trace=trace + ["agent_completed:budget_agent"])


def build_budget_response(result: dict, ok: bool, trace: list[str]) -> dict:
    """Construye una respuesta estable para la API."""
    messages = result.get("messages") or []
    quote_summary = result.get("quote_summary") or {}
    reply_text = getattr(messages[-1], "content", "") if messages else ""

    return {
        "ok": ok,
        "agent_name": "budget_agent",
        "reply_text": reply_text if ok else "",
        "sale_order_id": result.get("sale_order_id") or quote_summary.get("sale_order_id"),
        "normalized_request": result.get("normalized_request") or {},
        "quote_summary": quote_summary,
        "error": result.get("error"),
        "trace": trace,
    }


def build_budget_from_ticket_orchestrator() -> BudgetFromTicketOrchestrator:
    """Crea el orquestador de presupuestos."""
    return BudgetFromTicketOrchestrator()