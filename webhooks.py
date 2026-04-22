from __future__ import annotations

from dataclasses import dataclass
import re

from agents.budget_agent.dependencies import (
    BudgetDependencies,
)
from agents.budget_agent.dependencies import build_dependencies as build_budget_deps
from agents.budget_agent.graph import build_budget_graph
from odoo.api_wrapper import OdooAPIWrapper
from routing.semantic_router import router
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME


@dataclass(frozen=True)
class TicketWebhookOrchestrator:
    odoo_service_builder: callable
    budget_deps_builder: callable

    async def handle_ticket_created(
        self, ticket_id: int, thread_id: str | None = None, model: str | None = None
    ) -> dict:
        trace = [f"webhook_received:{ticket_id}", f"fetch_ticket:{ticket_id}"]
        odoo_service: OdooAPIWrapper = self.odoo_service_builder(model=model)
        ticket = odoo_service.get_helpdesk_ticket(ticket_id)
        if not ticket:
            return {
                "ok": False,
                "stage": "webhook",
                "error": f"No se encontró el ticket {ticket_id} en Odoo.",
                "route_name": None,
                "agent_name": None,
                "ticket": {},
                "normalized_request": {},
                "assistant_reply": "",
                "quote_summary": {},
                "chat_channel": {},
                "chat_message_id": None,
                "trace": trace + ["ticket_not_found"],
            }

        trace.append("ticket_loaded")
        route_name = router(build_ticket_text(ticket)).name
        trace.append(f"route_decided:{route_name}")

        chat_channel, bot_user = ensure_ticket_chat(odoo_service, ticket)
        trace.append(f"chat_ready:{chat_channel['id']}")

        if route_name != "budget":
            return {
                "ok": True,
                "stage": "routing",
                "error": None,
                "route_name": route_name,
                "agent_name": None,
                "ticket": ticket,
                "normalized_request": {},
                "assistant_reply": "",
                "quote_summary": {},
                "chat_channel": chat_channel,
                "chat_message_id": None,
                "trace": trace + ["no_agent_dispatched"],
            }

        normalized_request = build_budget_request_from_ticket(ticket)
        if not normalized_request["requirements"]:
            return {
                "ok": False,
                "stage": "routing",
                "error": "El ticket fue clasificado como budget, pero no se detectaron requisitos fiables.",
                "route_name": route_name,
                "agent_name": "budget_agent",
                "ticket": ticket,
                "normalized_request": normalized_request,
                "assistant_reply": "",
                "quote_summary": {},
                "chat_channel": chat_channel,
                "chat_message_id": None,
                "trace": trace + ["budget_request_incomplete"],
            }

        trace.append("budget_request_prepared")
        trace.append("dispatch_agent:budget_agent")
        budget_deps: BudgetDependencies = self.budget_deps_builder(model=model)
        budget_result = await build_budget_graph().ainvoke(
            {"normalized_request": normalized_request},
            config={"configurable": {"deps": budget_deps, "thread_id": thread_id}},
        )

        if budget_result.get("error"):
            return {
                "ok": False,
                "stage": "budget",
                "error": budget_result["error"],
                "route_name": route_name,
                "agent_name": "budget_agent",
                "ticket": ticket,
                "normalized_request": normalized_request,
                "assistant_reply": "",
                "quote_summary": {},
                "trace": trace + ["agent_failed:budget_agent"],
            }

        assistant_reply = ""
        messages = budget_result.get("messages", [])
        if messages:
            assistant_reply = getattr(messages[-1], "content", "") or ""
        trace.append("agent_response_ready")

        chat_message_id = odoo_service.post_message_to_channel(
            channel_id=chat_channel["id"],
            body=assistant_reply,
            author_id=extract_partner_id(bot_user),
        )

        return {
            "ok": True,
            "stage": "budget",
            "error": None,
            "route_name": route_name,
            "agent_name": "budget_agent",
            "ticket": ticket,
            "normalized_request": normalized_request,
            "assistant_reply": assistant_reply,
            "quote_summary": budget_result.get("quote_summary", {}),
            "chat_channel": chat_channel,
            "chat_message_id": chat_message_id,
            "trace": trace + ["message_sent_to_chat", "agent_completed:budget_agent"],
        }


def build_ticket_text(ticket: dict) -> str:
    subject = ticket.get("name", ticket.get("subject", ""))
    body = ticket.get("description", ticket.get("body", ""))
    sender = ticket.get("partner_email", ticket.get("email_from", ""))
    return f"Asunto: {subject}\nRemitente: {sender}\nMensaje: {body}".strip()


def build_budget_request_from_ticket(ticket: dict) -> dict:
    ticket_text = build_ticket_text(ticket).lower()
    requirements = extract_budget_requirements(ticket_text)
    return {
        "company_name": extract_company_name(ticket),
        "project_summary": ticket.get("name", ticket.get("subject", "")).strip(),
        "requirements": requirements,
        "urgency": "media",
    }


def ensure_ticket_chat(odoo_service: OdooAPIWrapper, ticket: dict) -> tuple[dict, dict]:
    bot_user = odoo_service.get_or_create_discuss_bot_user()
    recipient_partner_id = extract_recipient_partner_id(odoo_service, ticket)
    participant_ids = [recipient_partner_id, extract_partner_id(bot_user)]
    channel_name = f"Ticket {ticket.get('id', 'unknown')} - Assistant Chatbot"
    return odoo_service.open_direct_chat(participant_ids, channel_name), bot_user


def extract_partner_id(user: dict) -> int:
    partner_field = user.get("partner_id")
    if isinstance(partner_field, list):
        return partner_field[0]
    return int(partner_field)


def extract_recipient_partner_id(odoo_service: OdooAPIWrapper, ticket: dict) -> int:
    partner_field = ticket.get("partner_id")
    if isinstance(partner_field, list):
        return partner_field[0]
    if isinstance(partner_field, int):
        return partner_field

    email = ticket.get("partner_email", ticket.get("email_from", ""))
    partner = odoo_service.get_partner_by_email(email) if email else None
    if partner:
        return partner["id"]

    return odoo_service.create_contact(
        {
            "name": extract_company_name(ticket),
            "email": email or False,
            "company_type": "person",
        }
    )


def extract_company_name(ticket: dict) -> str:
    partner_name = ticket.get("partner_name")
    if partner_name:
        return str(partner_name).strip()
    email = ticket.get("partner_email", ticket.get("email_from", ""))
    if email and "@" in str(email):
        return str(email).split("@", 1)[0].strip() or "Desconocido"
    return "Desconocido"


def extract_budget_requirements(ticket_text: str) -> list[str]:
    patterns = (
        ("automatizacion comercial", ("automatizacion comercial", "automatización comercial")),
        ("crm", ("crm",)),
        ("helpdesk", ("helpdesk", "soporte")),
        ("sales", ("ventas", "sales")),
    )
    requirements: list[str] = []
    normalized_text = re.sub(r"\s+", " ", ticket_text.lower())
    for canonical, terms in patterns:
        if any(term in normalized_text for term in terms):
            requirements.append(canonical)
    return requirements


def build_odoo_service(model: str | None = None) -> OdooAPIWrapper:
    return OdooAPIWrapper(
        url=ODOO_BASE_URL,
        username=ODOO_USERNAME,
        password=ODOO_PASSWORD,
        db=ODOO_DB,
    )


def build_ticket_webhook_orchestrator() -> TicketWebhookOrchestrator:
    return TicketWebhookOrchestrator(
        odoo_service_builder=build_odoo_service,
        budget_deps_builder=build_budget_deps,
    )
