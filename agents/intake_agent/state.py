from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class IntakeState(TypedDict, total=False):
    """Estado compartido del agente intake."""
    messages: Annotated[list, add_messages]
    source_input: dict
    extracted_text: str
    sender_name: str
    sender_email: str
    normalized_request: dict
    ticket_type: str
    ticket_payload: dict
    customer_context: dict
    ticket_id: int
    final_text: str
    warnings: list[str]
    source_channel: str
    error: str | None