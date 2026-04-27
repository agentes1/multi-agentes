# Definimos workflow de los agentes
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents.budget_agent.nodes import (
    compose_budget_reply_node,
    create_odoo_quote_node,
    ensure_partner_node,
    error_node,
    prepare_budget_node,
)
from agents.budget_agent.state import BudgetState


# routing tras prepare_budget_node: si hay error cortocircuita al nodo de error
def _route_after_prepare(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "ensure_partner_node"


# routing tras ensure_partner_node: si hay error cortocircuita al nodo de error
def _route_after_partner(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "create_odoo_quote_node"


# workflow agente presupuestos
# nodos: funciones (agentes)
# edges: orden de ejecución
# state: datos que fluyen entre nodos
def build_budget_graph():
    builder = StateGraph(BudgetState)

    # nodo preparación productos
    builder.add_node("prepare_budget_node", prepare_budget_node)
    # nodo que crea o recupera el partner en odoo
    builder.add_node("ensure_partner_node", ensure_partner_node)
    # nodo que crea el presupuesto en odoo
    builder.add_node("create_odoo_quote_node", create_odoo_quote_node)
    # nodo que redacta una respuesta util para el usuario
    builder.add_node("compose_budget_reply_node", compose_budget_reply_node)
    # nodo terminal cuando el flujo no puede continuar
    builder.add_node("error_node", error_node)
    # orden del flujo
    builder.add_edge(START, "prepare_budget_node")
    # edge condicional: ¿hay productos válidos?
    builder.add_conditional_edges("prepare_budget_node", _route_after_prepare)
    # edge condicional: ¿se pudo obtener o crear el cliente?
    builder.add_conditional_edges("ensure_partner_node", _route_after_partner)
    # tras crear el presupuesto, se compone una respuesta final mas rica
    builder.add_edge("create_odoo_quote_node", "compose_budget_reply_node")
    builder.add_edge("compose_budget_reply_node", END)
    # si algo falla, termina en el nodo de error
    builder.add_edge("error_node", END)
    # sistema de checkpoints en memoria RAM
    checkpointer = InMemorySaver()

    # convertir en grafo ejecutable
    return builder.compile(checkpointer=checkpointer)
