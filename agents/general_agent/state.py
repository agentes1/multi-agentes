from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class GeneralState(TypedDict, total=False):
    """Estado compartido del agente general."""
    messages: Annotated[list, add_messages]
    input_text: str
    reply_text: str
    error: str | None