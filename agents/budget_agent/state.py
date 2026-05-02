from typing import Any, TypedDict

from langchain_core.messages import BaseMessage


# estado compartido del grafo
# contiene la entrada normalizada, mensajes internos y resultado final
class BudgetState(TypedDict, total=False):
    messages: list[BaseMessage]

    # ticket crudo recibido desde Odoo/Discuss; el agente de presupuestos lo normaliza
    ticket: dict[str, Any]
    ticket_text: str
    source_ticket_id: int
    # json normalizado por el propio budget_agent; se mantiene como entrada opcional para tests/herramientas
    normalized_request: dict[str, Any]
    # productos seleccionados a partir de los requisitos
    selected_products: list[dict[str, Any]]
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
