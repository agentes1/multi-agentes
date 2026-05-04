from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents.sales_agent.nodes import (
    compose_sales_reply_node,
    create_crm_opportunity_node,
    error_node,
    prepare_sales_node,
)
from agents.sales_agent.state import SalesState


def _route_after_prepare(state: SalesState) -> str:
    return "error_node" if state.get("error") else "create_crm_opportunity_node"


def _route_after_create(state: SalesState) -> str:
    return "error_node" if state.get("error") else "compose_sales_reply_node"


def build_sales_graph():
    builder = StateGraph(SalesState)

    builder.add_node("prepare_sales_node", prepare_sales_node)
    builder.add_node("create_crm_opportunity_node", create_crm_opportunity_node)
    builder.add_node("compose_sales_reply_node", compose_sales_reply_node)
    builder.add_node("error_node", error_node)

    builder.add_edge(START, "prepare_sales_node")
    builder.add_conditional_edges("prepare_sales_node", _route_after_prepare)
    builder.add_conditional_edges("create_crm_opportunity_node", _route_after_create)
    builder.add_edge("compose_sales_reply_node", END)
    builder.add_edge("error_node", END)

    return builder.compile(checkpointer=InMemorySaver())
