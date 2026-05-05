from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents.budget_agent.nodes import (
    compose_budget_reply_node,
    create_odoo_quote_node,
    error_node,
    prepare_budget_node,
)
from agents.budget_agent.state import BudgetState


def route_next(ok_node: str):
    """Devuelve error si el estado trae fallo; si no, continúa."""
    return lambda state: "error_node" if state.get("error") else ok_node


def build_budget_graph():
    graph = StateGraph(BudgetState)

    graph.add_node("prepare_budget_node", prepare_budget_node)
    graph.add_node("create_odoo_quote_node", create_odoo_quote_node)
    graph.add_node("compose_budget_reply_node", compose_budget_reply_node)
    graph.add_node("error_node", error_node)

    graph.add_edge(START, "prepare_budget_node")
    graph.add_conditional_edges("prepare_budget_node", route_next("create_odoo_quote_node"))
    graph.add_conditional_edges("create_odoo_quote_node", route_next("compose_budget_reply_node"))
    graph.add_edge("compose_budget_reply_node", END)
    graph.add_edge("error_node", END)

    return graph.compile(checkpointer=InMemorySaver())