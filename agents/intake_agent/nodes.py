import json

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from agents.intake_agent.dependencies import IntakeDependencies
from agents.intake_agent.state import IntakeState
from schemas.budget import NormalizedRequest
from shared.catalog import normalize_requirement


# helper para obtener dependencias inyectadas desde el config del grafo
def _get_deps(config: RunnableConfig) -> IntakeDependencies:
    deps = config.get("configurable", {}).get("deps")
    if deps is None:
        raise RuntimeError("IntakeDependencies no inyectadas en config")
    return deps


# convierte diferentes formatos de entrada (email, chat, etc) a texto uniforme
# error si la entrada está vacía o el canal no tiene campos mínimos
async def prepare_input_node(state: IntakeState, config: RunnableConfig) -> dict:
    source_input = state["source_input"]
    channel = source_input.get("channel", "unknown")

    if channel == "email":
        subject = source_input.get("subject", "")
        body = source_input.get("body", "")
        sender = source_input.get("from", "")

        # validación: un email sin asunto y sin cuerpo no tiene información útil
        if not subject and not body:
            return {
                "error": "Email recibido sin asunto ni cuerpo. No se puede procesar.",
            }

        text = f"""
Canal: email
Remitente: {sender}
Asunto: {subject}
Mensaje:
{body}
"""

    elif channel == "chat":
        user_name = source_input.get("user_name", "")
        message = source_input.get("message", "")
        company_name = source_input.get("company_name", "")

        # validación: un mensaje de chat vacío no tiene información útil
        if not message:
            return {
                "error": "Mensaje de chat recibido vacío. No se puede procesar.",
            }

        text = f"""
Canal: chat
Usuario: {user_name}
Empresa: {company_name}
Mensaje:
{message}
"""

    else:
        # fallback genérico para otros formatos no reconocidos
        text = str(source_input)

        # validación: si el fallback también queda vacío no podemos continuar
        if not text.strip():
            return {
                "error": f"Canal '{channel}' no reconocido y sin contenido procesable.",
            }

    return {
        "messages": [AIMessage(content="Entrada convertida a texto unificado")],
        "extracted_text": text.strip(),
        "error": None,
    }


# extrae del texto unificado un JSON estructurado usando el LLM
# error si el LLM no devuelve nada mínimamente aprovechable
async def extract_request_node(state: IntakeState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)
    extracted_text = state["extracted_text"]

    prompt = f"""
Eres un agente comercial que analiza mensajes de clientes y los transforma en solicitudes estructuradas para presupuestación.

Debes devolver un JSON válido con esta estructura exacta:
{{
  "company_name": "string",
  "project_summary": "string",
  "requirements": ["crm", "emails", "presupuestos", "odoo", "dashboard"],
  "urgency": "baja|media|alta",
  "missing_information": []
}}

Reglas:
- Solo puedes usar esos valores de requirements si aplican claramente
- No inventes datos
- Si el nombre de empresa no aparece claro, usa "Desconocido"
- Si falta información relevante, añádelo en missing_information
- Devuelve solo JSON válido, sin explicaciones

Texto del cliente:
{extracted_text}
"""

    response = await deps.llm.ainvoke([HumanMessage(content=prompt)])
    content = response.content if isinstance(response.content, str) else str(response.content)

    try:
        parsed = json.loads(content)
        normalized = NormalizedRequest.model_validate(parsed)
    except Exception:
        # si el LLM no devuelve JSON válido dos veces seguidas es un error real
        return {
            "error": "El LLM no devolvió un JSON válido tras el intento de extracción.",
        }

    # normaliza requisitos usando catálogo compartido para evitar sinónimos o variantes
    normalized_requirements = []
    for req in normalized.requirements:
        value = normalize_requirement(req)
        if value and value not in normalized_requirements:
            normalized_requirements.append(value)

    normalized.requirements = normalized_requirements

    return {
        "messages": [
            AIMessage(content=f"Solicitud estructurada generada para {normalized.company_name}")
        ],
        "normalized_request": normalized.model_dump(),
        "error": None,
    }


# valida que la solicitud normalizada tenga los campos mínimos necesarios
# no es bloqueante: los avisos se acumulan en validation_notes y el flujo continúa
async def validate_request_node(state: IntakeState, config: RunnableConfig) -> dict:
    normalized_request = state["normalized_request"]
    notes = []

    if normalized_request.get("company_name") == "Desconocido":
        notes.append("No se ha podido identificar claramente la empresa")
    if not normalized_request.get("requirements"):
        notes.append("No se han identificado requisitos funcionales claros")
    if not normalized_request.get("project_summary"):
        notes.append("No se ha podido resumir claramente la necesidad del cliente")

    return {
        "messages": [AIMessage(content="Solicitud validada")],
        "validation_notes": notes,
    }


# nodo terminal de error: se alcanza cuando prepare o extract detectan un fallo
# devuelve un normalized_request vacío para que el sistema receptor no rompa
async def error_node(state: IntakeState) -> dict:
    error_msg = state.get("error", "Error desconocido en el agente de intake")

    return {
        "messages": [AIMessage(content=f"No se ha podido procesar la entrada: {error_msg}")],
        "normalized_request": {},
        "validation_notes": [error_msg],
    }
