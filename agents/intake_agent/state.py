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

    # Resultado Odoo
    partner_id: int | None
    ticket_id: int | None

    # Control simple
    error: str | None