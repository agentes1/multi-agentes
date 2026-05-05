import json, re
from email.utils import parseaddr
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from agents.intake_agent.dependencies import IntakeDependencies
from agents.intake_agent.schemas import HelpdeskTicketSchema, IntakeRequestSchema
from agents.intake_agent.state import IntakeState
from shared.agent_notifications import notify_agent_progress
from shared.catalog import normalize_ticket_type, normalize_urgency
from shared.prompts import COMPANY_MATCHING_PROMPT, INTAKE_EXTRACTION_PROMPT

def get_deps(config: RunnableConfig) -> IntakeDependencies:
    """Recupera las dependencias del agente."""
    deps = config.get("configurable", {}).get("deps")
    if not deps: raise RuntimeError("IntakeDependencies no están configuradas")
    return deps

def clean(value: object) -> str:
    """Limpia texto básico."""
    return str(value or "").strip()

def clean_json(content: object) -> dict:
    """Limpia JSON aunque venga dentro de markdown."""
    text = str(content or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.IGNORECASE).strip()
    return json.loads(text)

def priority_from_urgency(urgency: str) -> str:
    """Convierte urgencia en prioridad de Odoo."""
    return {"baja": "0", "media": "1", "alta": "2"}.get(urgency, "1")

def ticket_catalog(ticket_type: str) -> tuple[str, str, str, list[str]]:
    """Mapea el tipo detectado al catálogo de Helpdesk."""
    return {"budget": ("Presupuestos", "Presupuesto", "Consulta presupuesto", []), "issue": ("Soporte cliente", "Soporte", "Problema", [])}.get(ticket_type, ("Soporte cliente", "Soporte", "Interno", ["Pendiente validación"]))

def email_to_text(source: dict) -> tuple[str, str, str]:
    """Convierte el email en texto único para el LLM."""
    raw_sender = source.get("from") or source.get("email_from") or ""
    parsed_name, parsed_email = parseaddr(raw_sender)
    sender_name = clean(source.get("sender_name") or source.get("author_name") or parsed_name)
    sender_email = clean(source.get("sender_email") or source.get("email") or source.get("email_from_address") or parsed_email).lower()
    text = f"Canal: email\nRemitente: {raw_sender}\nNombre remitente: {sender_name}\nEmail remitente: {sender_email}\nAsunto: {source.get('subject', '')}\nMensaje:\n{source.get('body', '')}"
    return text, sender_name, sender_email

def build_description(request: dict, company: dict | None, history: dict | None = None) -> str:
    """Crea la descripción interna del ticket."""
    lines = [
        f"Empresa detectada: {request.get('company_name') or 'No identificada'}",
        f"Empresa Odoo: {(company or {}).get('name') or 'No asociada'}",
        f"Contacto del correo: {request.get('sender_name') or 'No indicado'}",
        f"Email del correo: {request.get('sender_email') or 'No indicado'}", "",
        f"Resumen: {request.get('project_summary') or ''}",
    ]
    if request.get("requirements"): lines += ["", "Requisitos detectados:"] + [f"- {r}" for r in request["requirements"][:5]]
    if request.get("missing_information"): lines += ["", "Faltan datos:"] + [f"- {m}" for m in request["missing_information"][:3]]
    if history: lines += ["", "Historial Odoo:", f"- Pedidos encontrados: {len(history.get('orders', []))}", f"- Tickets anteriores encontrados: {len(history.get('tickets', []))}"]
    return "\n".join(lines)

def notify_progress(config: RunnableConfig, message: str, type_: str = "info") -> None:
    """Notifica el avance del agente."""
    notify_agent_progress(config=config, title="Agente Intake", message=message, type=type_)

def build_result(message: str, **extra) -> dict:
    """Devuelve un estado con mensaje interno."""
    return {"messages": [AIMessage(content=message)], **extra}

async def select_company(deps: IntakeDependencies, company_name: str) -> dict | None:
    """Busca empresas y deja que el LLM elija la mejor."""
    company_name = clean(company_name)
    if not company_name: return None
    companies = deps.odoo_mcp_client.find_company(name=company_name, exact=False, limit=20)
    if not companies: return None
    companies_text = "\n".join(f'- id={c["id"]}, name="{c["name"]}"' for c in companies)
    prompt = COMPANY_MATCHING_PROMPT.format(company_name=company_name, companies_text=companies_text)
    try:
        company_id = clean_json((await deps.llm.ainvoke([HumanMessage(content=prompt)])).content).get("company_id")
        company_id = int(company_id) if company_id is not None else None
    except Exception:
        return None
    return next((c for c in companies if int(c["id"]) == company_id), None)

async def prepare_input_node(state: IntakeState, config: RunnableConfig) -> dict:
    """Prepara el email recibido."""
    source = state["source_input"]
    if not source.get("subject") and not source.get("body"): return {"error": "Email recibido sin asunto ni cuerpo."}
    text, sender_name, sender_email = email_to_text(source)
    notify_progress(config, "Correo preparado correctamente.")
    return build_result("Email preparado", extracted_text=text, sender_name=sender_name, sender_email=sender_email, source_channel="email", error=None)

async def extract_request_node(state: IntakeState, config: RunnableConfig) -> dict:
    """Extrae la solicitud estructurada con el LLM."""
    notify_progress(config, "Analizando el contenido del correo...")
    deps = get_deps(config)
    prompt = INTAKE_EXTRACTION_PROMPT.format(email_text=state["extracted_text"])
    try:
        request = IntakeRequestSchema.model_validate(clean_json((await deps.llm.ainvoke([HumanMessage(content=prompt)])).content)).model_dump()
    except Exception as exc:
        return {"error": f"El LLM no devolvió una solicitud válida: {exc}"}
    request.update({
        "urgency": normalize_urgency(request.get("urgency")),
        "ticket_type": normalize_ticket_type(request.get("ticket_type")),
        "company_name": clean(request.get("company_name")),
        "sender_name": clean(state.get("sender_name")),
        "sender_email": clean(state.get("sender_email")).lower(),
    })
    notify_progress(config, f"Solicitud detectada: {request['ticket_type']} para {request['company_name'] or 'empresa no identificada'}.")
    return build_result(f"Solicitud extraída para {request['company_name'] or 'empresa no identificada'}", normalized_request=request, ticket_type=request["ticket_type"], sender_name=request["sender_name"], sender_email=request["sender_email"], error=None)

async def prepare_ticket_node(state: IntakeState, config: RunnableConfig) -> dict:
    """Prepara el payload final del ticket."""
    notify_progress(config, "Buscando empresa en Odoo y preparando el ticket...")
    deps, request = get_deps(config), state["normalized_request"]
    company = await select_company(deps, request["company_name"])
    company_id = company.get("id") if company else None
    history = deps.odoo_mcp_client.get_customer_history(company_id) if company_id else None
    team, type_name, category, tags = ticket_catalog(request["ticket_type"])
    tags = list(tags)
    if not company: tags.append("Cliente nuevo")
    if request.get("missing_information"): tags.append("Faltan datos")
    if request.get("urgency") == "alta": tags.append("Urgente")
    ticket_data = {
        "title": request["project_summary"],
        "description": build_description(request, company, history),
        "priority": priority_from_urgency(request["urgency"]),
        "team_name": team, "type_name": type_name, "category_name": category,
        "tag_names": list(dict.fromkeys(tags)), "motive_name": None,
        "company_id": company_id, "company_name": company.get("name") if company else None,
        "detected_company_name": request["company_name"],
        "partner_name": company.get("name") if company else "",
        "partner_email": request.get("sender_email", ""),
    }
    try:
        ticket = HelpdeskTicketSchema.model_validate(ticket_data).model_dump()
    except Exception as exc:
        return {"error": f"No se pudo preparar el ticket: {exc}"}
    notify_progress(config, f"Ticket preparado para el equipo {ticket['team_name']}.")
    return build_result(f"Ticket preparado para {ticket['team_name']}", ticket_payload=ticket, customer_context={"company": company, "customer_history": history}, error=None)

async def create_ticket_node(state: IntakeState, config: RunnableConfig) -> dict:
    """Crea el ticket real en Odoo."""
    notify_progress(config, "Creando ticket en Odoo...")
    deps = get_deps(config)
    ticket = HelpdeskTicketSchema.model_validate(state["ticket_payload"])
    warnings = []
    try:
        team = deps.odoo_mcp_client.find_helpdesk_team(ticket.team_name) or deps.odoo_mcp_client.find_helpdesk_team("Soporte cliente")
        if not team: raise ValueError("No existe equipo válido en Odoo.")
        ticket_type = deps.odoo_mcp_client.find_ticket_type(ticket.type_name)
        category = deps.odoo_mcp_client.find_ticket_category(ticket.category_name)
        tag_ids = deps.odoo_mcp_client.find_ticket_tags(ticket.tag_names)
        if not ticket_type: warnings.append(f"No existe tipo '{ticket.type_name}'")
        if not category: warnings.append(f"No existe categoría '{ticket.category_name}'")
        if ticket.tag_names and not tag_ids: warnings.append("No se resolvieron etiquetas")
        if not ticket.company_id and ticket.detected_company_name: warnings.append(f"Empresa '{ticket.detected_company_name}' no asociada")
        description = ticket.description + (("\n\nObservaciones:\n- " + "\n- ".join(warnings)) if warnings else "")
        ticket_id = deps.odoo_mcp_client.create_helpdesk_ticket(
            title=ticket.title, description=description, team_id=team["id"],
            priority=ticket.priority, type_id=ticket_type["id"] if ticket_type else None,
            category_id=category["id"] if category else None, tag_ids=tag_ids,
            partner_id=ticket.company_id, partner_name=ticket.partner_name,
            partner_email=ticket.partner_email, origin_channel="email",
        )
    except Exception as exc:
        notify_progress(config, f"Error al crear el ticket en Odoo: {exc}", "danger")
        return {"error": f"Error al crear el ticket en Odoo: {exc}"}
    notify_progress(config, f"Ticket creado correctamente con ID {ticket_id}.", "success")
    final_text = f"Ticket creado correctamente en Odoo con id {ticket_id} y tipo {state['ticket_type']}."
    return build_result(f"Ticket creado correctamente con id {ticket_id}", ticket_id=ticket_id, final_text=final_text, warnings=warnings, error=None)

async def error_node(state: IntakeState) -> dict:
    """Devuelve una respuesta controlada si falla el flujo."""
    error = state.get("error") or "Error desconocido en el agente de intake"
    return {"messages": [AIMessage(content=f"No se ha podido procesar la entrada: {error}")], "normalized_request": {}, "final_text": f"Error: {error}"}