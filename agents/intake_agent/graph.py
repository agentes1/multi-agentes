# Definimos workflow del agente input
from langgraph.graph import END, START, StateGraph

from agents.intake_agent.nodes import (
    error_node,
    extract_request_node,
    prepare_input_node,
    validate_request_node,
)
from agents.intake_agent.state import IntakeState


# routing tras prepare_input_node: si la entrada está vacía o el canal es desconocido
def _route_after_prepare(state: IntakeState) -> str:
    return "error_node" if state.get("error") else "extract_request_node"


# routing tras extract_request_node: si el LLM no pudo estructurar nada útil
def _route_after_extract(state: IntakeState) -> str:
    return "error_node" if state.get("error") else "validate_request_node"


# workflow agente intake
# nodos: funciones (agentes)
# edges: orden de ejecución
# state: datos que fluyen entre nodos
def build_intake_graph():
    builder = StateGraph(IntakeState)

    # nodo normalización del canal de entrada
    builder.add_node("prepare_input_node", prepare_input_node)
    # nodo extracción y estructuración con LLM
    builder.add_node("extract_request_node", extract_request_node)
    # nodo validación de campos obligatorios
    builder.add_node("validate_request_node", validate_request_node)
    # nodo terminal cuando el flujo no puede continuar
    builder.add_node("error_node", error_node)

    # orden del flujo
    builder.add_edge(START, "prepare_input_node")
    # edge condicional: ¿se pudo extraer texto de la entrada?
    builder.add_conditional_edges("prepare_input_node", _route_after_prepare)
    # edge condicional: ¿devolvió el LLM un JSON estructurado válido?
    builder.add_conditional_edges("extract_request_node", _route_after_extract)
    builder.add_edge("validate_request_node", END)
    builder.add_edge("error_node", END)

    # convertir en grafo ejecutable
    return builder.compile()
