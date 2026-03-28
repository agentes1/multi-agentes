from typing import Annotated, TypedDict

from langgraph.graph.message import (
    add_messages,  # para añadir el valor de las claves de estado en vez de sobreescribir
)


# definir estado compartido del grafo para intake
class IntakeState(TypedDict):
    # guarda el historial de mensajes del flujo
    messages: Annotated[list, add_messages]
    source_input: dict  # entrada cruda original (email, chat, etc)
    extracted_text: str  # texto unificado extraído de la entrada
    normalized_request: dict  # solicitud estructurada y validada
    validation_notes: list[str]  # avisos no bloqueantes sobre la solicitud
    error: str | None  # error producido en el flujo, None si no hay error
