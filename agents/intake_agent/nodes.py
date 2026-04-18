import json

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from agents.intake_agent.dependencies import IntakeDependencies
from agents.intake_agent.state import IntakeState
from shared.catalog import normalize_urgency, normalize_ticket_type


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
# además clasifica el mensaje como presupuesto, incidencia o descarte
async def extract_request_node(state: IntakeState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)
    extracted_text = state["extracted_text"]

    prompt = f"""
Eres un agente que analiza mensajes de clientes y los transforma en solicitudes estructuradas para procesarlas después.

Debes devolver un JSON válido con esta estructura exacta:
{{
  "company_name": "string",
  "project_summary": "string",
  "requirements": ["string"],
  "urgency": "string",
  "ticket_type": "budget|issue|discard",
  "missing_information": []
}}

Significado de ticket_type:
- "budget": el cliente pide presupuesto, propuesta, precio, implantación o módulos
- "issue": el cliente reporta un problema, error, incidencia o soporte
- "discard": el mensaje no contiene una petición útil o clara

Reglas:
- No inventes datos
- Conserva los requisitos tal como los identifiques semánticamente
- Si falta información relevante, añádelo en missing_information
- Si no hay una necesidad clara, usa ticket_type = "discard"
- Devuelve solo JSON válido, sin explicaciones

Texto del cliente:
{extracted_text}
"""

    response = await deps.llm.ainvoke([HumanMessage(content=prompt)])
    content = response.content if isinstance(response.content, str) else str(response.content)

    try:
        parsed = json.loads(content)
    except Exception:
        return {
            "error": "El LLM no devolvió un JSON válido tras el intento de extracción.",
        }

    # validación mínima de estructura
    required_keys = {
        "company_name",
        "project_summary",
        "requirements",
        "urgency",
        "ticket_type",
        "missing_information",
    }
    if not required_keys.issubset(parsed.keys()):
        return {
            "error": "El JSON generado no contiene todos los campos obligatorios.",
        }

    # normaliza urgencia a valores cerrados
    parsed["urgency"] = normalize_urgency(parsed.get("urgency", ""))

    # normaliza tipo de ticket a valores cerrados
    parsed["ticket_type"] = normalize_ticket_type(parsed.get("ticket_type", ""))

    # limpieza mínima para evitar estructuras inesperadas
    if not isinstance(parsed.get("requirements"), list):
        parsed["requirements"] = []

    if not isinstance(parsed.get("missing_information"), list):
        parsed["missing_information"] = []

    return {
        "messages": [
            AIMessage(
                content=(
                    f"Solicitud estructurada generada para {parsed['company_name']} "
                    f"con tipo {parsed['ticket_type']} y urgencia {parsed['urgency']}"
                )
            )
        ],
        "normalized_request": parsed,
        "ticket_type": parsed["ticket_type"],
        "error": None,
    }

# prepara los datos del ticket según la solicitud estructurada
# aquí ya se hace el mapeo directo a los valores que existen realmente en tu Odoo local
async def prepare_ticket_node(state: IntakeState, config: RunnableConfig) -> dict:
    normalized_request = state["normalized_request"]

    company_name = normalized_request.get("company_name", "Desconocido")
    project_summary = normalized_request.get("project_summary", "").strip()
    requirements = normalized_request.get("requirements", [])
    urgency = normalized_request.get("urgency", "media")
    ticket_type = normalized_request.get("ticket_type", "discard")
    missing_information = normalized_request.get("missing_information", [])

    # validación: necesitamos al menos un resumen mínimo para crear ticket
    if not project_summary:
        return {
            "error": "La solicitud no contiene un resumen suficiente para crear el ticket.",
        }

    # mapeo simple y directo al catálogo real que has creado en Odoo
    if ticket_type == "budget":
        team_name = "Presupuestos"
        type_name = "Presupuesto"
        category_name = "Consulta presupuesto"
        tag_names = ["Cliente nuevo"]

    elif ticket_type == "issue":
        team_name = "Soporte cliente"
        type_name = "Soporte"
        category_name = "Problema"
        tag_names = []

    else:
        # los mensajes poco claros van a soporte para revisión manual
        team_name = "Soporte cliente"
        type_name = "Soporte"
        category_name = "Interno"
        tag_names = ["Pendiente validación"]

    # mapeo de urgencia a prioridad real del módulo helpdesk_mgmt
    # 0 = baja, 1 = media, 2 = alta
    urgency_to_priority = {
        "baja": "0",
        "media": "1",
        "alta": "2",
    }
    priority = urgency_to_priority.get(urgency, "1")

    # si faltan datos relevantes marcamos una etiqueta adicional
    if missing_information and "Faltan datos" not in tag_names:
        tag_names.append("Faltan datos")

    # si la urgencia es alta añadimos también la etiqueta Urgente
    if urgency == "alta" and "Urgente" not in tag_names:
        tag_names.append("Urgente")

    # descripción corta y útil en texto plano
    description_lines = [
        f"Empresa: {company_name}",
        "",
        f"Resumen: {project_summary}",
    ]

    if requirements:
        description_lines.append("")
        description_lines.append("Requisitos detectados:")
        description_lines.extend([f"- {req}" for req in requirements[:5]])

    if missing_information:
        description_lines.append("")
        description_lines.append("Faltan datos:")
        description_lines.extend([f"- {note}" for note in missing_information[:3]])


    ticket_payload = {
        "title": project_summary,
        "description": "\n".join(description_lines),
        "priority": priority,
        "team_name": team_name,
        "type_name": type_name,
        "category_name": category_name,
        "tag_names": tag_names,
        "motive_name": None,
    }

    return {
        "messages": [
            AIMessage(
                content=f"Ticket preparado para el equipo {team_name}"
            )
        ],
        "ticket_payload": ticket_payload,
        "error": None,
    }


# crea el ticket en Odoo usando los modelos reales del módulo helpdesk de OCA
# resuelve nombres a ids antes de crear el ticket para no depender de textos sueltos
async def create_ticket_node(state: IntakeState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)

    ticket_payload = state["ticket_payload"]
    ticket_type = state["ticket_type"]
    warnings = []

    try:
        # resolver equipo; si no existe usamos uno por defecto
        team_id = deps.odoo_service.get_team_id_by_name(ticket_payload["team_name"])
        if not team_id:
            warnings.append(
                f"No existe el equipo '{ticket_payload['team_name']}' en Odoo. Se usará el equipo por defecto."
            )
            team_id = deps.odoo_service.get_team_id_by_name("Soporte cliente")

        if not team_id:
            raise ValueError("No existe tampoco el equipo por defecto 'Soporte cliente' en Odoo")

        # resolver tipo de ticket; si no existe se omite
        type_id = deps.odoo_service.get_ticket_type_id_by_name(ticket_payload["type_name"])
        if not type_id:
            warnings.append(
                f"No existe el tipo de ticket '{ticket_payload['type_name']}' en Odoo. Se creará sin tipo."
            )
            type_id = None

        # resolver categoría; si no existe se omite
        category_id = deps.odoo_service.get_category_id_by_name(ticket_payload["category_name"])
        if not category_id:
            warnings.append(
                f"No existe la categoría '{ticket_payload['category_name']}' en Odoo. Se creará sin categoría."
            )
            category_id = None

        # resolver etiquetas; si alguna no existe simplemente no se añade
        tag_ids = deps.odoo_service.get_tag_ids_by_names(ticket_payload["tag_names"])
        if ticket_payload.get("tag_names") and not tag_ids:
            warnings.append("No se pudo resolver ninguna de las etiquetas indicadas.")

        # resolver motivo solo si se ha informado; si no existe se omite
        motive_id = None
        if ticket_payload.get("motive_name"):
            motive_id = deps.odoo_service.get_motive_id_by_name_and_team(
                ticket_payload["motive_name"],
                team_id,
            )
            if not motive_id:
                warnings.append(
                    f"No existe el motivo '{ticket_payload['motive_name']}' para el equipo seleccionado. Se creará sin motivo."
                )

        # ampliar descripción con warnings si los hay
        description = ticket_payload["description"]
        if warnings:
            description += "\n\n---\nObservaciones automáticas:\n- " + "\n- ".join(warnings)

        # crear ticket real en helpdesk.ticket
        ticket_id = deps.odoo_service.create_helpdesk_ticket(
            title=ticket_payload["title"],
            description=description,
            team_id=team_id,
            priority=ticket_payload["priority"],
            type_id=type_id,
            category_id=category_id,
            tag_ids=tag_ids,
            motive_id=motive_id,
        )

    except Exception as e:
        return {
            "error": f"Error al crear el ticket en Odoo: {e}",
        }

    return {
        "messages": [
            AIMessage(content=f"Ticket creado correctamente con id {ticket_id}")
        ],
        "ticket_id": ticket_id,
        "final_text": (
            f"Ticket creado correctamente en Odoo con id {ticket_id} "
            f"y tipo {ticket_type}."
        ),
        "warnings": warnings,
        "error": None,
    }


# nodo terminal de error: se alcanza cuando un nodo anterior detecta un fallo
async def error_node(state: IntakeState) -> dict:
    error_msg = state.get("error", "Error desconocido en el agente de intake")

    return {
        "messages": [AIMessage(content=f"No se ha podido procesar la entrada: {error_msg}")],
        "normalized_request": {},
        "final_text": f"Error: {error_msg}",
    }