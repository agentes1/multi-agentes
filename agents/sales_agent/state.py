from typing import Any, TypedDict

from langchain_core.messages import BaseMessage


class SalesState(TypedDict, total=False):
    messages: list[BaseMessage]
    ticket: dict[str, Any]
    ticket_text: str
    normalized_request: dict[str, Any]
    partner_id: int
    customer_profile: dict[str, Any]
    customer_history: dict[str, Any]
    crm_lead_id: int
    crm_summary: dict[str, Any]
    error: str
