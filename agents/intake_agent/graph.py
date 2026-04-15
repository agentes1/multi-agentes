# Definimos workflow del agente input
from langgraph.graph import END, START, StateGraph

from agents.intake_agent.nodes import (
    create_ticket_node,
    error_node,
    extract_request_node,
    prepare_input_node,
    prepare_ticket_node,
)
from agents.intake_agent.state import IntakeState


# routing tras prepare_input_node:
# si la entrada está vacía o no se ha podido convertir a texto, se corta el flujo
def _route_after_prepare(state: IntakeState) -> str:
    return "error_node" if state.get("error") else "extract_request_node"


# routing tras extract_request_node:
# si el LLM no ha podido devolver una estructura válida, se corta el flujo
def _route_after_extract(state: IntakeState) -> str:
    return "error_node" if state.get("error") else "prepare_ticket_node"


# routing tras prepare_ticket_node:
# si no hay datos suficientes para construir el ticket, se corta el flujo
def _route_after_prepare_ticket(state: IntakeState) -> str:
    return "error_node" if state.get("error") else "create_ticket_node"


# routing tras create_ticket_node:
# si Odoo falla al crear el ticket, terminamos en error; si no, finalizamos
def _route_after_create_ticket(state: IntakeState) -> str:
    return "error_node" if state.get("error") else END


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
    # nodo preparación de los datos finales del ticket
    builder.add_node("prepare_ticket_node", prepare_ticket_node)
    # nodo creación real del ticket en Odoo
    builder.add_node("create_ticket_node", create_ticket_node)
    # nodo terminal cuando el flujo no puede continuar
    builder.add_node("error_node", error_node)
    # orden del flujo
    builder.add_edge(START, "prepare_input_node")
    # edge condicional: ¿se pudo extraer texto de la entrada?
    builder.add_conditional_edges("prepare_input_node", _route_after_prepare)
    # edge condicional: ¿devolvió el LLM un JSON estructurado válido?
    builder.add_conditional_edges("extract_request_node", _route_after_extract)
    # edge condicional: ¿se pudo construir el payload del ticket?
    builder.add_conditional_edges("prepare_ticket_node", _route_after_prepare_ticket)
    # edge condicional: ¿se creó correctamente el ticket en Odoo?
    builder.add_conditional_edges("create_ticket_node", _route_after_create_ticket)
    # salida de error
    builder.add_edge("error_node", END)
    # convertir en grafo ejecutable
    return builder.compile()