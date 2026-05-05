from typing import Any, TypedDict

from langchain_core.messages import BaseMessage


class BudgetState(TypedDict, total=False):
    """Estado compartido entre nodos del agente."""

    messages: list[BaseMessage]

    ticket: dict[str, Any]
    ticket_text: str
    ticket_block: str
    source_text: str
    source_ticket_id: int

    normalized_request: dict[str, Any]
    selected_products: list[dict[str, Any]]
    unmatched_requirements: list[str]

    partner_id: int
    sale_order_id: int
    quote_summary: dict[str, Any]

    error: str