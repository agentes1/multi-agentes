from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agents.intake_agent.dependencies import build_dependencies as build_intake_deps
from agents.intake_agent.graph import build_intake_graph


@dataclass(frozen=True)
class IncomingEmailOrchestrator:
    """Orquesta correos entrantes y delega la creación del ticket en intake."""

    intake_deps_builder: Callable = build_intake_deps

    async def handle_incoming_email(self, payload: dict, thread_id: str | None = None) -> dict:
        """Adapta el email al estado inicial del agente intake."""
        trace = ["incoming_email_received"]
        deps = self.intake_deps_builder()
        source_input = build_email_source_input(payload)
        thread_id = thread_id or f"incoming-email-{payload.get('inbox_id', 'unknown')}"

        partner_id = payload.get("notify_partner_id") or payload.get("partner_id") or payload.get("author_id")

        if partner_id:
            from shared.odoo_notifier import OdooNotifier
            OdooNotifier().notify_partner(
                partner_id=partner_id,
                title="Agente Intake",
                message="Se ha recibido un nuevo correo. Iniciando procesamiento...",
                type="info",
            )

        result = await build_intake_graph().ainvoke(
            {"source_input": source_input},
            config={
                "configurable": {
                    "deps": deps,
                    "thread_id": thread_id,
                    "partner_id": partner_id,
                }
            },
        )
        if result.get("error"):
            return build_email_response(result, ok=False, trace=trace + ["intake_failed"])

        trace += [f"ticket_type_decided:{result.get('ticket_type', 'unknown')}", f"ticket_created:{result.get('ticket_id')}", "email_reply_skipped"]
        return build_email_response(result, ok=True, trace=trace)


def build_email_source_input(payload: dict) -> dict:
    """Normaliza el payload recibido desde Odoo."""
    return {
        "channel": "email",
        "subject": payload.get("subject") or "",
        "body": payload.get("body") or payload.get("body_html") or "",
        "from": payload.get("email_from") or "",
        "email_from": payload.get("email_from") or "",
        "sender_name": payload.get("sender_name") or "",
        "email_to": payload.get("email_to") or "",
        "email_cc": payload.get("email_cc") or "",
        "message_id": payload.get("message_id") or "",
        "received_date": payload.get("received_date") or "",
    }


def build_email_response(result: dict, ok: bool, trace: list[str]) -> dict:
    """Construye una respuesta estable para Odoo."""
    return {
        "ok": ok,
        "ticket_id": result.get("ticket_id"),
        "final_text": result.get("final_text") or "",
        "reply_text": "",
        "route_name": None,
        "agent_name": None,
        "normalized_request": result.get("normalized_request") or {},
        "ticket_payload": result.get("ticket_payload") or {},
        "quote_summary": {},
        "warnings": result.get("warnings") or [],
        "error": result.get("error"),
        "trace": trace,
    }


def build_incoming_email_orchestrator() -> IncomingEmailOrchestrator:
    """Crea el orquestador de correos."""
    return IncomingEmailOrchestrator()
