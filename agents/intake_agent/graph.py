# Definimos workflow del agente input
from langgraph.graph import END, START, StateGraph

from agents.intake_agent.nodes import (
    extract_request_node,
    prepare_input_node,
    validate_request_node,
)
from agents.intake_agent.state import IntakeState


# workflow agente presupuestos
# nodos: funciones (agentes)
# edges: orden de ejecución
# state: datos que fluyen entre nodos
def build_intake_graph():
    builder = StateGraph(IntakeState)

    builder.add_node("prepare_input_node", prepare_input_node)
    builder.add_node("extract_request_node", extract_request_node)
    builder.add_node("validate_request_node", validate_request_node)

    # orden del flujo
    builder.add_edge(START, "prepare_input_node")
    builder.add_edge("prepare_input_node", "extract_request_node")
    builder.add_edge("extract_request_node", "validate_request_node")
    builder.add_edge("validate_request_node", END)

    # convertir en grafo ejecutable
    return builder.compile()
