# Definimos workflow de los agentes
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents.budget_agent.nodes import (
    error_node,
    persist_memory_node,
    prepare_budget_node,
    pricing_node,
    render_quote_node,
    retrieve_memory_node,
)
from agents.budget_agent.state import BudgetState


# routing tras prepare_budget_node: si hay error cortocircuita al nodo de error
def _route_after_prepare(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "retrieve_memory_node"


# routing tras pricing_node: si el MCP falló cortocircuita al nodo de error
def _route_after_pricing(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "render_quote_node"


# workflow agente presupuestos
# nodos: funciones (agentes)
# edges: orden de ejecución
# state: datos que fluyen entre nodos
def build_budget_graph():
    builder = StateGraph(BudgetState)

    # nodo preparación productos
    builder.add_node("prepare_budget_node", prepare_budget_node)
    # nodo de memoria
    builder.add_node("retrieve_memory_node", retrieve_memory_node)
    # nodo de cálculo
    builder.add_node("pricing_node", pricing_node)
    # genera texto final
    builder.add_node("render_quote_node", render_quote_node)
    # guarda histórico (después de render para tener el final_text completo)
    builder.add_node("persist_memory_node", persist_memory_node)
    # nodo terminal cuando el flujo no puede continuar
    builder.add_node("error_node", error_node)

    # orden del flujo
    builder.add_edge(START, "prepare_budget_node")
    # edge condicional: ¿hay productos válidos?
    builder.add_conditional_edges("prepare_budget_node", _route_after_prepare)
    builder.add_edge("retrieve_memory_node", "pricing_node")
    # edge condicional: ¿respondió el MCP correctamente?
    builder.add_conditional_edges("pricing_node", _route_after_pricing)
    builder.add_edge("render_quote_node", "persist_memory_node")
    builder.add_edge("persist_memory_node", END)
    builder.add_edge("error_node", END)

    # sistema de checkpoints en memoria RAM
    checkpointer = InMemorySaver()
    # convertir en grafo ejecutable
    return builder.compile(checkpointer=checkpointer)
