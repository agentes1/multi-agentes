# Definimos workflow de los agentes
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents.budget_agent.nodes import (
    persist_memory_node,
    prepare_budget_node,
    pricing_node,
    render_quote_node,
    retrieve_memory_node,
)
from agents.budget_agent.state import BudgetState


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
    # guarda histórico
    builder.add_node("persist_memory_node", persist_memory_node)
    # genera texto final
    builder.add_node("render_quote_node", render_quote_node)

    # orden del flujo
    builder.add_edge(START, "prepare_budget_node")
    builder.add_edge("prepare_budget_node", "retrieve_memory_node")
    builder.add_edge("retrieve_memory_node", "pricing_node")
    builder.add_edge("pricing_node", "persist_memory_node")
    builder.add_edge("persist_memory_node", "render_quote_node")
    builder.add_edge("render_quote_node", END)

    # sistema de checkpoints en memoria RAM
    checkpointer = InMemorySaver()
    # convertir en grafo ejecutable
    return builder.compile(checkpointer=checkpointer)
