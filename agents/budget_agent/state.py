from typing import Any, TypedDict

from langchain_core.messages import BaseMessage


class BudgetState(TypedDict, total=False):
    messages: list[BaseMessage]

    # json ya normalizado por el agente anterior
    normalized_request: dict[str, Any]
    # contexto enriquecido por enrich_context_node via tool-calling (solo lectura)
    odoo_context: dict[str, Any]
    # productos seleccionados a partir de los requisitos
    selected_products: list[dict]
    # requisitos del cliente sin producto coincidente en Odoo
    unmatched_requirements: list[str]
    # id del contacto/cliente en odoo
    partner_id: int
    # id del presupuesto creado en odoo
    sale_order_id: int
    # resumen simple del presupuesto creado
    quote_summary: dict[str, Any]

    # error si algo falla durante el flujo
    error: str | None
