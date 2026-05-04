from __future__ import annotations

import json
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agents.sales_agent.dependencies import SalesDependencies
from agents.sales_agent.state import SalesState
from shared.prompts import ANSWER_BOT_PROMPT, SALES_REPLY_PROMPT, SALES_TICKET_EXTRACTION_PROMPT


def get_deps(config: RunnableConfig) -> SalesDependencies:
    deps = config.get("configurable", {}).get("deps")
    if not deps:
        raise RuntimeError("SalesDependencies no están configuradas")
    return deps


def clean_json(content: object) -> dict:
    text = str(content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def ticket_to_text(ticket: dict) -> str:
    fields = {
        "Ticket ID": ticket.get("id"),
        "Título": ticket.get("name") or ticket.get("subject"),
        "Descripción": ticket.get("description") or ticket.get("body"),
        "Cliente": ticket.get("partner_name"),
        "Email": ticket.get("partner_email") or ticket.get("email_from"),
        "partner_id": ticket.get("partner_id"),
    }
    return "\n".join(f"{key}: {value}" for key, value in fields.items() if value)


def _build_opportunity_title(ticket: dict, request: dict) -> str:
    company_name = str(request.get("company_name") or ticket.get("partner_name") or "").strip()
    summary = str(request.get("sales_summary") or ticket.get("name") or ticket.get("title") or "").strip()
    summary = re.sub(r"\s+", " ", summary)
    if company_name and summary:
        return f"{company_name} - {summary[:80]}"
    return summary[:100] or "Oportunidad comercial"


def _build_opportunity_priority(request: dict) -> str:
    goals = [str(goal).strip().lower() for goal in (request.get("commercial_goals") or []) if str(goal).strip()]
    if len(goals) >= 3:
        return "2"
    if any(term in goal for goal in goals for term in ("pipeline", "automatizacion", "automatización", "lead")):
        return "2"
    return "1"


def _build_crm_description(ticket: dict, request: dict, customer_profile: dict, customer_history: dict) -> str:
    description_parts = []

    summary = str(request.get("sales_summary") or "").strip()
    goals = [str(goal).strip() for goal in (request.get("commercial_goals") or []) if str(goal).strip()]
    next_step = str(request.get("next_step") or "").strip()
    original_request = str(ticket.get("description") or "").strip()

    if summary:
        description_parts.append(f"Resumen comercial: {summary}")
    if goals:
        description_parts.append("Objetivos comerciales:\n- " + "\n- ".join(goals))
    if next_step:
        description_parts.append(f"Siguiente paso sugerido: {next_step}")

    if customer_profile:
        profile_lines = []
        if customer_profile.get("known_customer") is not None:
            profile_lines.append(f"Cliente conocido: {'sí' if customer_profile.get('known_customer') else 'no'}")
        if customer_profile.get("segment"):
            profile_lines.append(f"Segmento: {customer_profile.get('segment')}")
        if customer_profile.get("email"):
            profile_lines.append(f"Email cliente: {customer_profile.get('email')}")
        if profile_lines:
            description_parts.append("Perfil cliente:\n- " + "\n- ".join(profile_lines))

    if customer_history:
        orders = customer_history.get("orders") or []
        tickets = customer_history.get("tickets") or []
        history_lines = [f"Pedidos previos: {len(orders)}", f"Tickets previos: {len(tickets)}"]
        if orders:
            last_order = orders[0]
            history_lines.append(f"Último pedido: {last_order.get('name') or last_order.get('id')}")
        description_parts.append("Historial reciente:\n- " + "\n- ".join(history_lines))

    if original_request:
        description_parts.append("Solicitud original:\n" + original_request)

    return "\n\n".join(part for part in description_parts if part).strip()


async def extract_sales_request(llm, ticket_text: str) -> dict:
    response = await llm.ainvoke([HumanMessage(content=SALES_TICKET_EXTRACTION_PROMPT.format(ticket_text=ticket_text))])
    return clean_json(response.content)


async def prepare_sales_node(state: SalesState, config: RunnableConfig) -> dict:
    deps = get_deps(config)
    ticket = state.get("ticket") or {}
    ticket_text = state.get("ticket_text") or ticket_to_text(ticket)

    if not ticket_text:
        return {"error": "No se recibió contenido del ticket para crear la oportunidad comercial."}

    try:
        request = state.get("normalized_request") or await extract_sales_request(deps.llm, ticket_text)
    except Exception as exc:
        return {"error": f"No se pudieron extraer los datos comerciales del ticket: {exc}"}

    goals = request.get("commercial_goals") or []
    if not goals:
        return {"error": "El ticket no contiene objetivos comerciales suficientes para crear la oportunidad."}

    partner_id = ticket.get("partner_id")
    company_name = str(request.get("company_name") or ticket.get("partner_name") or "").strip()
    customer_email = str(ticket.get("partner_email") or "").strip() or None

    try:
        if not partner_id and company_name:
            partner_id = deps.odoo_mcp_client.get_or_create_contact(company_name, customer_email)
        customer_profile = deps.odoo_mcp_client.get_customer_profile(company_name) if company_name else {}
        customer_history = (
            deps.odoo_mcp_client.get_customer_history(int(partner_id), limit=5)
            if partner_id
            else {}
        )
    except Exception as exc:
        return {"error": f"No se pudo resolver el contacto comercial en Odoo: {exc}"}

    return {
        "messages": [AIMessage(content=f"Oportunidad comercial preparada con {len(goals)} objetivos.")],
        "ticket_text": ticket_text,
        "normalized_request": request,
        "partner_id": int(partner_id) if partner_id else None,
        "customer_profile": customer_profile,
        "customer_history": customer_history,
        "error": None,
    }


async def create_crm_opportunity_node(state: SalesState, config: RunnableConfig) -> dict:
    deps = get_deps(config)
    ticket = state.get("ticket") or {}
    request = state.get("normalized_request") or {}
    ticket_id = ticket.get("id")

    try:
        existing = deps.odoo_mcp_client.find_crm_opportunity_by_source_ticket(int(ticket_id)) if ticket_id else None
        if existing:
            return {
                "messages": [AIMessage(content="La oportunidad comercial ya existía en CRM.")],
                "crm_lead_id": existing.get("id"),
                "crm_summary": existing,
                "error": None,
            }

        title = _build_opportunity_title(ticket, request)
        description = _build_crm_description(
            ticket=ticket,
            request=request,
            customer_profile=state.get("customer_profile") or {},
            customer_history=state.get("customer_history") or {},
        )
        priority = _build_opportunity_priority(request)

        opportunity_id = deps.odoo_mcp_client.create_crm_opportunity(
            title=title,
            description=description,
            partner_id=state.get("partner_id"),
            partner_name=str(ticket.get("partner_name") or request.get("company_name") or "").strip() or None,
            partner_email=str(ticket.get("partner_email") or "").strip() or None,
            source_ticket_id=ticket_id,
            priority=priority,
        )
        opportunity = deps.odoo_mcp_client.get_crm_opportunity(opportunity_id) or {"id": opportunity_id}
    except Exception as exc:
        return {"error": f"Error creando oportunidad comercial en CRM: {exc}"}

    return {
        "messages": [AIMessage(content=f"Oportunidad CRM creada. ID={opportunity_id}")],
        "crm_lead_id": opportunity_id,
        "crm_summary": opportunity,
        "error": None,
    }


async def compose_sales_reply_node(state: SalesState, config: RunnableConfig) -> dict:
    deps = get_deps(config)
    request = state.get("normalized_request") or {}
    crm_summary = state.get("crm_summary") or {}
    company_name = (
        str(request.get("company_name") or state.get("ticket", {}).get("partner_name") or "cliente").strip()
    )

    prompt = SALES_REPLY_PROMPT.format(
        company_name=company_name,
        sales_summary=request.get("sales_summary") or "Sin resumen adicional",
        commercial_goals=", ".join(request.get("commercial_goals") or []) or "No disponible",
        next_step=request.get("next_step") or "Revisión comercial",
        crm_summary=crm_summary,
    )

    try:
        response = await deps.llm.ainvoke([SystemMessage(content=ANSWER_BOT_PROMPT), HumanMessage(content=prompt)])
        reply_text = str(response.content or "").strip()
    except Exception:
        reply_text = (
            f"He creado la oportunidad comercial en CRM para {company_name}. "
            "El siguiente paso recomendado es revisar el alcance comercial y continuar el seguimiento."
        )

    return {"messages": [AIMessage(content=reply_text)], "final_reply": reply_text}


async def error_node(state: SalesState) -> dict:
    error = state.get("error") or "Error desconocido en el agente de ventas"
    return {"messages": [AIMessage(content=f"No se ha podido crear la oportunidad comercial: {error}")]}
