from langgraph.graph import END, START, StateGraph
from agents.intake_agent.nodes import create_ticket_node, error_node, extract_request_node, prepare_input_node, prepare_ticket_node
from agents.intake_agent.state import IntakeState

def route_next(ok_node: str):
    """Devuelve error si el estado trae fallo; si no, continúa."""
    return lambda state: "error_node" if state.get("error") else ok_node

def build_intake_graph():
    """Construye el flujo del agente intake."""
    graph = StateGraph(IntakeState)
    graph.add_node("prepare_input_node", prepare_input_node)
    graph.add_node("extract_request_node", extract_request_node)
    graph.add_node("prepare_ticket_node", prepare_ticket_node)
    graph.add_node("create_ticket_node", create_ticket_node)
    graph.add_node("error_node", error_node)
    graph.add_edge(START, "prepare_input_node")
    graph.add_conditional_edges("prepare_input_node", route_next("extract_request_node"))
    graph.add_conditional_edges("extract_request_node", route_next("prepare_ticket_node"))
    graph.add_conditional_edges("prepare_ticket_node", route_next("create_ticket_node"))
    graph.add_conditional_edges("create_ticket_node", route_next(END))
    graph.add_edge("error_node", END)
    return graph.compile()