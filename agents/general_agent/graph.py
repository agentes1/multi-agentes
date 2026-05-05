from langgraph.graph import END, START, StateGraph
from agents.general_agent.nodes import error_node, respond_node
from agents.general_agent.state import GeneralState

def route_after_respond(state: GeneralState) -> str:
    """Envía a error si el nodo dejó fallo."""
    return "error_node" if state.get("error") else END

def build_general_graph():
    """Construye el flujo simple del agente general."""
    graph = StateGraph(GeneralState)
    graph.add_node("respond_node", respond_node)
    graph.add_node("error_node", error_node)
    graph.add_edge(START, "respond_node")
    graph.add_conditional_edges("respond_node", route_after_respond)
    graph.add_edge("error_node", END)
    return graph.compile()