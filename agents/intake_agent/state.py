from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class IntakeState(TypedDict):
    messages: Annotated[list, add_messages]
    source_input: dict
    extracted_text: str
    normalized_request: dict
    validation_notes: list[str]
