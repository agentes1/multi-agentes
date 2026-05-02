from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents.budget_agent.nodes import (
    compose_budget_reply_node,
    create_odoo_quote_node,
    error_node,
    prepare_budget_node,
)
from agents.budget_agent.state import BudgetState


def _route_after_prepare(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "create_odoo_quote_node"


def _route_after_create_quote(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "compose_budget_reply_node"


def build_budget_graph():
    builder = StateGraph(BudgetState)

    # Lee el ticket aceptado, normaliza la petición y selecciona productos reales.
    builder.add_node("prepare_budget_node", prepare_budget_node)

    # Crea o reutiliza el presupuesto de Odoo asociado al ticket.
    builder.add_node("create_odoo_quote_node", create_odoo_quote_node)

    # Al final se genera una respuesta para informar del presupuesto creado.
    builder.add_node("compose_budget_reply_node", compose_budget_reply_node)

    # Nodo común para cortar el flujo si algún paso falla.
    builder.add_node("error_node", error_node)

    builder.add_edge(START, "prepare_budget_node")
    builder.add_conditional_edges("prepare_budget_node", _route_after_prepare)

    builder.add_conditional_edges("create_odoo_quote_node", _route_after_create_quote)

    builder.add_edge("compose_budget_reply_node", END)
    builder.add_edge("error_node", END)

    return builder.compile(checkpointer=InMemorySaver())
