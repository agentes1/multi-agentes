from langgraph.graph import END, START, StateGraph

from .nodes import (
    create_ticket_node,
    ensure_partner_node,
    normalize_email_node,
    resolve_sender_node,
    resolve_ticket_fields_node,
)
from .state import TicketAgentState


def build_ticket_graph():
    graph = StateGraph(TicketAgentState)

    graph.add_node("normalize_email", normalize_email_node)
    graph.add_node("resolve_sender", resolve_sender_node)
    graph.add_node("ensure_partner", ensure_partner_node)
    graph.add_node("resolve_ticket_fields", resolve_ticket_fields_node)
    graph.add_node("create_ticket", create_ticket_node)

    graph.add_edge(START, "normalize_email")
    graph.add_edge("normalize_email", "resolve_sender")
    graph.add_edge("resolve_sender", "ensure_partner")
    graph.add_edge("ensure_partner", "resolve_ticket_fields")
    graph.add_edge("resolve_ticket_fields", "create_ticket")
    graph.add_edge("create_ticket", END)

    return graph.compile()
