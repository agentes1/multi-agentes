import json
from email.utils import parseaddr

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from agents.intake_agent.dependencies import IntakeDependencies
from agents.intake_agent.schemas import HelpdeskTicketSchema, IntakeRequestSchema
from agents.intake_agent.state import IntakeState
from shared.catalog import normalize_ticket_type, normalize_urgency
from shared.prompts import COMPANY_MATCHING_PROMPT, INTAKE_EXTRACTION_PROMPT


def _get_deps(config: RunnableConfig) -> IntakeDependencies:
    """Obtiene las dependencias inyectadas en el grafo."""
    deps = config.get("configurable", {}).get("deps")
    if deps is None:
        raise RuntimeError("IntakeDependencies no inyectadas en config")
    return deps


def _clean(value: object) -> str:
    """Convierte un valor a texto y elimina espacios sobrantes."""
    return str(value or "").strip()


def _json_content(response) -> str:
    """Devuelve el contenido textual de una respuesta del LLM."""
    return response.content if isinstance(response.content, str) else str(response.content)


def _priority_from_urgency(urgency: str) -> str:
    """Convierte la urgencia normalizada en la prioridad usada por Odoo."""
    return {"baja": "0", "media": "1", "alta": "2"}.get(urgency, "1")


def _catalog_from_ticket_type(ticket_type: str) -> tuple[str, str, str, list[str]]:
    """Devuelve equipo, tipo, categoría y etiquetas base según el tipo de ticket."""
    if ticket_type == "budget":
        return "Presupuestos", "Presupuesto", "Consulta presupuesto", []

    if ticket_type == "issue":
        return "Soporte cliente", "Soporte", "Problema", []

    return "Soporte cliente", "Soporte", "Interno", ["Pendiente validación"]


def _build_email_text(source_input: dict) -> tuple[str, str, str]:
    """Convierte el email recibido en un texto simple para que lo analice el LLM."""
    subject = source_input.get("subject", "")
    body = source_input.get("body", "")
    raw_sender = source_input.get("from", "") or source_input.get("email_from", "")
    parsed_name, parsed_email = parseaddr(raw_sender)

    sender_name = (
        source_input.get("sender_name")
        or source_input.get("author_name")
        or parsed_name
        or ""
    )
    sender_email = (
        source_input.get("sender_email")
        or source_input.get("email")
        or source_input.get("email_from_address")
        or parsed_email
        or ""
    )

    text = (
        f"Canal: email\n"
        f"Remitente: {raw_sender}\n"
        f"Nombre remitente: {sender_name}\n"
        f"Email remitente: {sender_email}\n"
        f"Asunto: {subject}\n"
        f"Mensaje:\n{body}"
    )

    return text, _clean(sender_name), _clean(sender_email).lower()


def _build_description(
    detected_company_name: str,
    company_name: str | None,
    sender_name: str,
    sender_email: str,
    project_summary: str,
    requirements: list[str],
    missing_information: list[str],
) -> str:
    """Crea la descripción que se guardará en el ticket de Odoo."""
    lines = [
        f"Empresa detectada: {detected_company_name or 'No identificada'}",
        f"Empresa Odoo: {company_name or 'No asociada'}",
    ]

    if sender_name:
        lines.append(f"Contacto del correo: {sender_name}")

    if sender_email:
        lines.append(f"Email del correo: {sender_email}")

    lines.extend(["", f"Resumen: {project_summary}"])

    if requirements:
        lines.extend(["", "Requisitos detectados:"])
        lines.extend(f"- {item}" for item in requirements[:5])

    if missing_information:
        lines.extend(["", "Faltan datos:"])
        lines.extend(f"- {item}" for item in missing_information[:3])

    return "\n".join(lines)


async def prepare_input_node(state: IntakeState, config: RunnableConfig) -> dict:
    """Prepara el email recibido para que el LLM pueda analizarlo."""
    source_input = state["source_input"]

    if not source_input.get("subject") and not source_input.get("body"):
        return {"error": "Email recibido sin asunto ni cuerpo. No se puede procesar."}

    text, sender_name, sender_email = _build_email_text(source_input)

    return {
        "messages": [AIMessage(content="Email convertido a texto unificado")],
        "extracted_text": text,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "source_channel": "email",
        "error": None,
    }


async def extract_request_node(state: IntakeState, config: RunnableConfig) -> dict:
    """Extrae empresa, resumen, requisitos, urgencia y tipo de ticket desde el email."""
    deps = _get_deps(config)

    sender_name = _clean(state.get("sender_name", ""))
    sender_email = _clean(state.get("sender_email", "")).lower()
    prompt = INTAKE_EXTRACTION_PROMPT.format(email_text=state["extracted_text"])

    response = await deps.llm.ainvoke([HumanMessage(content=prompt)])

    try:
        request = IntakeRequestSchema.model_validate(json.loads(_json_content(response))).model_dump()
    except Exception:
        return {"error": "El LLM no devolvió un JSON válido tras el intento de extracción."}

    request["urgency"] = normalize_urgency(request["urgency"])
    request["ticket_type"] = normalize_ticket_type(request["ticket_type"])
    request["company_name"] = _clean(request["company_name"])
    request["sender_name"] = sender_name
    request["sender_email"] = sender_email

    return {
        "messages": [
            AIMessage(
                content=f"Solicitud estructurada generada para {request['company_name'] or 'empresa no identificada'}"
            )
        ],
        "normalized_request": request,
        "ticket_type": request["ticket_type"],
        "sender_name": sender_name,
        "sender_email": sender_email,
        "error": None,
    }


async def _select_existing_company_with_llm(
    deps: IntakeDependencies,
    company_name: str,
) -> dict | None:
    """Busca en Odoo la empresa existente más parecida a la empresa detectada."""
    company_name = _clean(company_name)
    if not company_name:
        return None

    companies = deps.odoo_service.search_read(
        "res.partner",
        [("is_company", "=", True), ("active", "=", True)],
        fields=["id", "name"],
        limit=200,
    )
    if not companies:
        return None

    companies_text = "\n".join(
        f'- id={company["id"]}, name="{company["name"]}"'
        for company in companies
    )
    prompt = COMPANY_MATCHING_PROMPT.format(
        company_name=company_name,
        companies_text=companies_text,
    )

    response = await deps.llm.ainvoke([HumanMessage(content=prompt)])

    try:
        selected_id = json.loads(_json_content(response)).get("company_id")
        selected_id = int(selected_id) if selected_id is not None else None
    except Exception:
        return None

    return next(
        (company for company in companies if int(company["id"]) == selected_id),
        None,
    )


async def prepare_ticket_node(state: IntakeState, config: RunnableConfig) -> dict:
    """Prepara el payload del ticket antes de crearlo en Odoo."""
    deps = _get_deps(config)
    request = state["normalized_request"]

    company = await _select_existing_company_with_llm(deps, request["company_name"])
    company_id = company["id"] if company else None
    company_name = company["name"] if company else None

    team_name, type_name, category_name, tag_names = _catalog_from_ticket_type(
        request["ticket_type"]
    )

    if not company:
        tag_names.append("Cliente nuevo")
    if request["missing_information"]:
        tag_names.append("Faltan datos")
    if request["urgency"] == "alta":
        tag_names.append("Urgente")

    ticket_data = {
        "title": request["project_summary"],
        "description": _build_description(
            detected_company_name=request["company_name"],
            company_name=company_name,
            sender_name=request.get("sender_name", ""),
            sender_email=request.get("sender_email", ""),
            project_summary=request["project_summary"],
            requirements=request["requirements"],
            missing_information=request["missing_information"],
        ),
        "priority": _priority_from_urgency(request["urgency"]),
        "team_name": team_name,
        "type_name": type_name,
        "category_name": category_name,
        "tag_names": list(dict.fromkeys(tag_names)),
        "motive_name": None,
        "company_id": company_id,
        "company_name": company_name,
        "detected_company_name": request["company_name"],
        "partner_name": company_name or "",
        "partner_email": request.get("sender_email", ""),
    }

    try:
        ticket = HelpdeskTicketSchema.model_validate(ticket_data).model_dump()
    except Exception:
        return {"error": "No se pudo preparar un payload válido para el ticket."}

    return {
        "messages": [
            AIMessage(
                content=(
                    f"Ticket preparado para el equipo {ticket['team_name']}. "
                    f"Empresa asociada: {ticket['company_name'] or 'No asociada'}"
                )
            )
        ],
        "ticket_payload": ticket,
        "error": None,
    }


async def create_ticket_node(state: IntakeState, config: RunnableConfig) -> dict:
    """Crea el ticket real en Odoo usando los datos preparados."""
    deps = _get_deps(config)
    ticket = HelpdeskTicketSchema.model_validate(state["ticket_payload"])
    warnings = []

    try:
        team_id = deps.odoo_service.get_team_id_by_name(ticket.team_name)
        if not team_id:
            warnings.append(f"No existe el equipo '{ticket.team_name}'. Se usará Soporte cliente.")
            team_id = deps.odoo_service.get_team_id_by_name("Soporte cliente")
        if not team_id:
            raise ValueError("No existe el equipo por defecto 'Soporte cliente' en Odoo.")

        type_id = deps.odoo_service.get_ticket_type_id_by_name(ticket.type_name)
        category_id = deps.odoo_service.get_category_id_by_name(ticket.category_name)
        tag_ids = deps.odoo_service.get_tag_ids_by_names(ticket.tag_names)
        motive_id = (
            deps.odoo_service.get_motive_id_by_name_and_team(ticket.motive_name, team_id)
            if ticket.motive_name
            else None
        )

        if not type_id:
            warnings.append(f"No existe el tipo '{ticket.type_name}'. Se creará sin tipo.")
        if not category_id:
            warnings.append(f"No existe la categoría '{ticket.category_name}'. Se creará sin categoría.")
        if ticket.tag_names and not tag_ids:
            warnings.append("No se pudo resolver ninguna de las etiquetas indicadas.")
        if not ticket.company_id and ticket.detected_company_name:
            warnings.append(
                f"Empresa detectada '{ticket.detected_company_name}', pero no se asoció ninguna compañía existente."
            )

        description = ticket.description
        if warnings:
            description += "\n\nObservaciones automáticas:\n- " + "\n- ".join(warnings)

        ticket_id = deps.odoo_service.create_helpdesk_ticket(
            title=ticket.title,
            description=description,
            team_id=team_id,
            priority=ticket.priority,
            type_id=type_id,
            category_id=category_id,
            tag_ids=tag_ids,
            motive_id=motive_id,
            partner_id=ticket.company_id,
            partner_name=ticket.partner_name,
            partner_email=ticket.partner_email,
            origin_channel="email",
        )

    except Exception as exc:
        return {"error": f"Error al crear el ticket en Odoo: {exc}"}

    return {
        "messages": [AIMessage(content=f"Ticket creado correctamente con id {ticket_id}")],
        "ticket_id": ticket_id,
        "final_text": f"Ticket creado correctamente en Odoo con id {ticket_id} y tipo {state['ticket_type']}.",
        "warnings": warnings,
        "error": None,
    }


async def error_node(state: IntakeState) -> dict:
    """Devuelve un error controlado cuando el flujo no puede continuar."""
    error_msg = state.get("error", "Error desconocido en el agente de intake")
    return {
        "messages": [AIMessage(content=f"No se ha podido procesar la entrada: {error_msg}")],
        "normalized_request": {},
        "final_text": f"Error: {error_msg}",
    }