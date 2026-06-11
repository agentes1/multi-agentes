from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


class RAGState(TypedDict, total=False):
    """Estado del agente RAG."""
    messages: Annotated[list, add_messages]
    input_text: str
    retrieved_tickets: list[dict]
    reply_text: str
    error: str | None