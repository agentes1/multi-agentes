from typing import Any, TypedDict

from langchain_core.messages import BaseMessage


# estado compartido del grafo
# contiene la entrada normalizada, mensajes internos y resultado final
class BudgetState(TypedDict, total=False):
    messages: list[BaseMessage]

    # json ya normalizado por el agente anterior
    normalized_request: dict[str, Any]
    # productos seleccionados a partir de los requisitos
    selected_products: list[str]
    # id del contacto/cliente en odoo
    partner_id: int
    # id del presupuesto creado en odoo
    sale_order_id: int
    # resumen simple del presupuesto creado
    quote_summary: dict[str, Any]
    # requisitos que no se han podido mapear a producto real
    unmatched_requirements: list[str]

    # error si algo falla durante el flujo
    error: str
