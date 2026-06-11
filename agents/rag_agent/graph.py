from langgraph.graph import END, START, StateGraph

from agents.rag_agent.nodes import error_node, respond_node, retrieve_node
from agents.rag_agent.state import RAGState


def route_after_retrieve(state: RAGState) -> str:
    """Va a error si hay fallo, si no continúa a respond."""
    return "error_node" if state.get("error") else "respond_node"


def build_rag_graph():
    """Construye el flujo del agente RAG."""
    graph = StateGraph(RAGState)

    graph.add_node("retrieve_node", retrieve_node)
    graph.add_node("respond_node", respond_node)
    graph.add_node("error_node", error_node)

    graph.add_edge(START, "retrieve_node")
    graph.add_conditional_edges("retrieve_node", route_after_retrieve)
    graph.add_edge("respond_node", END)
    graph.add_edge("error_node", END)

    return graph.compile()