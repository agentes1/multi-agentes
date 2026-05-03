from typing import Annotated, TypedDict

from langgraph.graph.message import (
    add_messages,  # para añadir el valor de las claves de estado en vez de sobreescribir
)


# definir estado compartido del grafo para intake
class IntakeState(TypedDict, total=False):
    # guarda el historial de mensajes del flujo
    messages: Annotated[list, add_messages]
    # entrada cruda original (email, chat, etc)
    source_input: dict
    # texto unificado extraído de la entrada
    extracted_text: str
    # datos básicos del remitente para flujos de email
    sender_name: str
    sender_email: str
    # solicitud estructurada generada por el LLM
    normalized_request: dict
    # tipo de ticket detectado por el agente: budget, issue o discard
    ticket_type: str
    # datos finales preparados para crear el ticket en Odoo
    ticket_payload: dict
    # id del ticket creado en Odoo
    ticket_id: int
    # texto final del resultado del flujo
    final_text: str
    # warnings, faltan datos importantes en el ticket
    warnings: list[str]
    # canal de origen normalizado (email, chat, etc)
    source_channel: str
    # error producido en el flujo, None o ausencia si no hay error
    error: str | None
