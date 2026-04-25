from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from odoo.helpers import Table
from shared.catalog import (
    CANONICAL_TYPE_TO_ODOO_NAME,
    DEFAULT_TICKET,
    PRIORITY_TO_ODOO,
    normalize_priority,
    normalize_ticket_type,
)
from shared.prompts import PARTNER_NAME_PROMPT, COMPANY_MATCH_PROMPT, NORMALIZATION_SYSTEM_PROMPT

from .dependencies import TicketAgentDependencies
from .schemas import Ticket
from .state import TicketAgentState


def _clean(value: Any) -> str | None:
    """Limpia valores vacíos para evitar guardar strings con espacios."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _deps(config: RunnableConfig) -> TicketAgentDependencies:
    """Obtiene las dependencias del agente desde la configuración del grafo."""
    return config["configurable"]["deps"]


def _split_email(email: str) -> tuple[str, str]:
    """Separa el email en usuario y dominio para ayudar a detectar la empresa."""
    email = email.strip().lower()
    if "@" not in email:
        return "", ""
    local, domain = email.split("@", 1)
    return local, domain.split(".")[0]


async def normalize_email_node(state: TicketAgentState, config: RunnableConfig) -> dict[str, Any]:
    """Convierte el correo recibido en un objeto Ticket estructurado."""
    subject = state.get("email_subject") or ""
    body = state.get("email_body") or ""
    sender_email = state.get("sender_email") or ""
    sender_name = state.get("sender_name")

    try:
        ticket = await _deps(config).structured_llm.ainvoke([
            SystemMessage(content=NORMALIZATION_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Asunto: {subject}\n"
                f"Remitente nombre: {sender_name}\n"
                f"Remitente email: {sender_email}\n"
                f"Cuerpo:\n{body}"
            )),
        ])
        ticket = ticket if isinstance(ticket, Ticket) else Ticket.model_validate(ticket)
    except Exception as e:
        return {"error": f"No se pudo estructurar el correo: {e}"}

    title = _clean(ticket.title)
    description = _clean(ticket.description)

    if not title:
        return {"error": "El LLM no devolvió un título válido."}
    if not description:
        return {"error": "El LLM no devolvió una descripción válida."}

    return {
        "ticket": ticket.model_copy(update={
            "title": title,
            "description": description,
            "customer_email": _clean(ticket.customer_email) or _clean(sender_email),
            "company_name": None,
            "partner_name": None,
            "team": _clean(ticket.team),
            "ticket_type": _clean(ticket.ticket_type),
            "category": _clean(ticket.category),
            "priority": _clean(ticket.priority),
            "tags": [_clean(t) for t in ticket.tags if _clean(t)],
        }),
    }


async def resolve_sender_node(state: TicketAgentState, config: RunnableConfig) -> dict[str, Any]:
    """Resuelve la empresa y el nombre del contacto a partir del remitente."""
    if state.get("error") or not state.get("ticket"):
        return {}

    deps = _deps(config)
    ticket = state["ticket"]
    sender_email = _clean(state.get("sender_email")) or ""
    sender_name = _clean(state.get("sender_name"))
    local_part, domain_hint = _split_email(sender_email)

    all_companies: list[str] = []

    try:
        records = deps.odoo_service.search_read(
            Table.Contact,
            [("is_company", "=", True)],
            ["name"],
            limit=200,
        )
        all_companies = [r["name"] for r in records if r.get("name")]
    except Exception:
        pass

    company_name: str | None = None

    if domain_hint and all_companies:
        try:
            response = await deps.llm.ainvoke([HumanMessage(
                content=COMPANY_MATCH_PROMPT.format(
                    domain=domain_hint,
                    companies="\n".join(f"- {c}" for c in all_companies),
                )
            )])
            chosen = _clean(getattr(response, "content", None) or str(response))
            if chosen and chosen.upper() != "NINGUNA" and chosen in all_companies:
                company_name = chosen
        except Exception:
            pass

    if not company_name and domain_hint:
        company_name = domain_hint.capitalize()

    partner_name = sender_name

    if not partner_name and local_part:
        try:
            response = await deps.llm.ainvoke([HumanMessage(
                content=PARTNER_NAME_PROMPT.format(local_part=local_part)
            )])
            partner_name = _clean(getattr(response, "content", None) or str(response))
        except Exception:
            pass

    missing_fields = []

    if not company_name:
        missing_fields.append("Compañía")
    if not ticket.ticket_type:
        missing_fields.append("Tipo de ticket")

    return {
        "ticket": ticket.model_copy(update={
            "company_name": company_name,
            "partner_name": partner_name,
            "missing_fields": missing_fields,
        }),
    }


async def ensure_partner_node(state: TicketAgentState, config: RunnableConfig) -> dict[str, Any]:
    """Busca la empresa en Odoo o la crea si no existe."""
    if state.get("error") or not state.get("ticket"):
        return {}

    service = _deps(config).odoo_service
    ticket = state["ticket"]
    email = str(ticket.customer_email) if ticket.customer_email else None
    company_name = ticket.company_name

    if not email and not company_name:
        return {"ticket": ticket}

    results = service.find_company(company_name, exact=True, limit=1) if company_name else []

    if not results and company_name:
        results = service.find_company(company_name, exact=False, limit=1)

    if results:
        company = results[0]
        return {
            "ticket": ticket.model_copy(update={
                "partner_id": company["id"],
                "company_name": company["name"],
                "company_is_new": False,
            }),
        }

    final_name = company_name or "Cliente nuevo"

    return {
        "ticket": ticket.model_copy(update={
            "partner_id": service.create_company_contact(final_name, email=email),
            "company_name": final_name,
            "company_is_new": True,
        }),
    }


def resolve_ticket_fields_node(state: TicketAgentState, config: RunnableConfig) -> dict[str, Any]:
    """Traduce valores de negocio a IDs reales de Odoo."""
    if state.get("error") or not state.get("ticket"):
        return {}

    service = _deps(config).odoo_service
    ticket = state["ticket"]

    normalized_type = normalize_ticket_type(ticket.ticket_type or "")
    normalized_priority = normalize_priority(ticket.priority or "")
    catalog_type = DEFAULT_TICKET.get(normalized_type, DEFAULT_TICKET["discard"])

    team_name = _clean(ticket.team) or _clean(state.get("team_name")) or catalog_type["team_name"]
    ticket_type_name = CANONICAL_TYPE_TO_ODOO_NAME.get(normalized_type, catalog_type["ticket_type"])
    category_name = _clean(ticket.category) or catalog_type["category"]

    tag_names = [
        *ticket.tags,
        *(["Cliente nuevo"] if ticket.company_is_new else []),
        *(["Faltan datos"] if ticket.missing_fields else []),
        *(["Urgente"] if normalized_priority == "alta" else []),
    ]

    return {
        "ticket": ticket.model_copy(update={
            "priority_odoo": PRIORITY_TO_ODOO.get(normalized_priority, PRIORITY_TO_ODOO["media"]),
            "team_id": service.find_record_id(Table.TicketTeam, team_name),
            "type_id": service.find_record_id(Table.TicketType, ticket_type_name),
            "category_id": service.find_record_id(Table.TicketCategory, category_name),
            "tag_ids": service.find_record_ids(Table.TicketTag, tag_names),
        }),
    }


def create_ticket_node(state: TicketAgentState, config: RunnableConfig) -> dict[str, Any]:
    """Construye el payload final y crea el ticket en Odoo."""
    if state.get("error") or not state.get("ticket"):
        return {}

    service = _deps(config).odoo_service
    ticket = state["ticket"]
    allowed_fields = service.get_model_fields(Table.Ticket)

    description = ticket.description

    if ticket.missing_fields:
        description += "\n\nDatos que faltan:\n- " + "\n- ".join(ticket.missing_fields)

    payload = {
        "name": ticket.title,
        "description": description,
        "priority": ticket.priority_odoo,
        "partner_id": ticket.partner_id,
        "partner_email": str(ticket.customer_email) if ticket.customer_email else None,
        "partner_name": ticket.partner_name,
        "team_id": ticket.team_id,
        "type_id": ticket.type_id,
        "category_id": ticket.category_id,
        "tag_ids": [(6, 0, ticket.tag_ids)] if ticket.tag_ids else None,
    }

    ticket_vals = {
        k: v
        for k, v in payload.items()
        if k in allowed_fields and v is not None
    }

    if not ticket_vals.get("name"):
        return {"error": "No se pudo construir el ticket: falta el campo 'name'."}

    return {
        "ticket_id": service.create_ticket_from_vals(ticket_vals),
        "ticket_vals": ticket_vals,
    }