from typing import Any, TypedDict


class TicketAgentState(TypedDict, total=False):
    # Entrada
    email_subject: str
    email_body: str
    sender_email: str
    sender_name: str | None
    team_name: str | None

    # Salida de normalización
    normalized_ticket: dict[str, Any]
    missing_fields: list[str]

    # Contexto enriquecido por enrich_context_node via tool-calling (solo lectura)
    odoo_context: dict[str, Any]

    # Resoluciones Odoo
    partner_id: int | None
    company_is_new: bool
    debug_trace: dict[str, Any]
    resolved_fields: dict[str, Any]
    ticket_vals: dict[str, Any]

    # Resultado final
    ticket_id: int | None
    error: str | None
