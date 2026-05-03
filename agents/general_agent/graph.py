from langgraph.graph import END, START, StateGraph

from agents.general_agent.nodes import error_node, respond_node
from agents.general_agent.state import GeneralState


def _route_after_respond(state: GeneralState) -> str:
    return "error_node" if state.get("error") else END


def build_general_graph():
    builder = StateGraph(GeneralState)

    builder.add_node("respond_node", respond_node)
    builder.add_node("error_node", error_node)

    builder.add_edge(START, "respond_node")
    builder.add_conditional_edges("respond_node", _route_after_respond)
    builder.add_edge("error_node", END)

    return builder.compile()
