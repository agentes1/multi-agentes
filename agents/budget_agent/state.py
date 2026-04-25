from typing import Any, TypedDict

from langchain_core.messages import BaseMessage

from agents.budget_agent.schemas import Budget


class BudgetState(TypedDict, total=False):
    messages: list[BaseMessage]

    # Datos de entrada recibidos desde el ticket
    ticket: dict[str, Any]
    ticket_title: str
    ticket_description: str
    company_name: str

    # Objeto principal del agente de presupuestos
    budget: Budget

    # id del presupuesto creado en Odoo
    sale_order_id: int

    # resumen simple del presupuesto creado
    quote_summary: dict[str, Any]

    # error si algo falla durante el flujo
    error: str | None