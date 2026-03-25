import json

from langchain_core.messages import AIMessage, HumanMessage

from agents.intake_agent.state import IntakeState
from schemas.budget import NormalizedRequest
from shared.catalog import normalize_requirement
from shared.llm import get_llm

llm = get_llm()


# convierte diferentes formatos de entrada (email, chat, etc) a texto uniforme
async def prepare_input_node(state: IntakeState) -> dict:
    source_input = state["source_input"]
    channel = source_input.get("channel", "unknown")

    if channel == "email":
        subject = source_input.get("subject", "")
        body = source_input.get("body", "")
        sender = source_input.get("from", "")

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

        text = f"""
Canal: chat
Usuario: {user_name}
Empresa: {company_name}
Mensaje:
{message}
"""
    else:
        # Fallback genérico para otros formatos
        text = str(source_input)

    return {
        "messages": [AIMessage(content="Entrada convertida a texto unificado")],
        "extracted_text": text.strip(),
    }


# obtener de cualquier texto un JSON estructurado
async def extract_request_node(state: IntakeState) -> dict:
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

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    content = response.content if isinstance(response.content, str) else str(response.content)

    try:
        parsed = json.loads(content)
        normalized = NormalizedRequest.model_validate(parsed)
    except Exception:
        # Fallback si el LLM no devuelve JSON válido
        normalized = NormalizedRequest(
            company_name="Desconocido",
            project_summary=extracted_text[:200],
            requirements=[],
            urgency="media",
            missing_information=["No se pudo parsear correctamente la solicitud"],
        )

    # Normaliza requisitos usando catálogo compartido
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
    }


async def validate_request_node(state: IntakeState) -> dict:
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
