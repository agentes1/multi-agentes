from langgraph.graph import START, END, StateGraph

from .state import TicketAgentState
from .nodes import (
    normalize_email_node,
    ensure_partner_node,
    create_ticket_node,
)


def build_ticket_graph():
    graph = StateGraph(TicketAgentState)

    graph.add_node("normalize_email", normalize_email_node)
    graph.add_node("ensure_partner", ensure_partner_node)
    graph.add_node("create_ticket", create_ticket_node)

    graph.add_edge(START, "normalize_email")
    graph.add_edge("normalize_email", "ensure_partner")
    graph.add_edge("ensure_partner", "create_ticket")
    graph.add_edge("create_ticket", END)

    return graph.compile()