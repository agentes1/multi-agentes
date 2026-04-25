from typing import Any, TypedDict

from .schemas import Ticket


class TicketAgentState(TypedDict, total=False):
    email_subject: str
    email_body: str
    sender_email: str
    sender_name: str | None
    team_name: str | None

    ticket: Ticket
    ticket_vals: dict[str, Any]
    ticket_id: int | None
    error: str | None
