from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents.budget_agent.nodes import (
    normalize_budget_node,
    resolve_products_node,
    ensure_partner_node,
    create_quote_node,
    error_node,
)
from agents.budget_agent.state import BudgetState


def _route_after_normalize(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "resolve_products_node"


def _route_after_products(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "ensure_partner_node"


def _route_after_partner(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "create_quote_node"


def _route_after_quote(state: BudgetState) -> str:
    return "error_node" if state.get("error") else END


def build_budget_graph():
    builder = StateGraph(BudgetState)

    builder.add_node("normalize_budget_node", normalize_budget_node)
    builder.add_node("resolve_products_node", resolve_products_node)
    builder.add_node("ensure_partner_node", ensure_partner_node)
    builder.add_node("create_quote_node", create_quote_node)
    builder.add_node("error_node", error_node)

    builder.add_edge(START, "normalize_budget_node")
    builder.add_conditional_edges("normalize_budget_node", _route_after_normalize)
    builder.add_conditional_edges("resolve_products_node", _route_after_products)
    builder.add_conditional_edges("ensure_partner_node", _route_after_partner)
    builder.add_conditional_edges("create_quote_node", _route_after_quote)
    builder.add_edge("error_node", END)

    return builder.compile(checkpointer=InMemorySaver())