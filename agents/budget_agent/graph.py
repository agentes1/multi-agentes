from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents.budget_agent.nodes import (
    enrich_context_node,
    error_node,
    prepare_budget_node,
    ensure_partner_node,
    create_odoo_quote_node,
)
from agents.budget_agent.state import BudgetState


def _route_after_enrich(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "prepare_budget_node"


def _route_after_prepare(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "ensure_partner_node"


def _route_after_partner(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "create_odoo_quote_node"


def build_budget_graph():
    builder = StateGraph(BudgetState)

    builder.add_node("enrich_context_node", enrich_context_node)
    builder.add_node("prepare_budget_node", prepare_budget_node)
    builder.add_node("ensure_partner_node", ensure_partner_node)
    builder.add_node("create_odoo_quote_node", create_odoo_quote_node)
    builder.add_node("error_node", error_node)

    builder.add_edge(START, "enrich_context_node")
    builder.add_conditional_edges("enrich_context_node", _route_after_enrich)
    builder.add_conditional_edges("prepare_budget_node", _route_after_prepare)
    builder.add_conditional_edges("ensure_partner_node", _route_after_partner)
    builder.add_edge("create_odoo_quote_node", END)
    builder.add_edge("error_node", END)

    return builder.compile(checkpointer=InMemorySaver())
