"""Orquestación del flujo de correo entrante.

mail_inbox_input registra el correo en Odoo y llama al endpoint del backend.
Este orquestador adapta ese payload al formato esperado por intake_agent,
deja que intake cree el ticket y devuelve el resultado a Odoo.
"""

from agents.intake_agent.dependencies import build_dependencies as build_intake_dependencies
from agents.intake_agent.graph import build_intake_graph


class IncomingEmailOrchestrator:
    def __init__(self, intake_deps_builder=build_intake_dependencies):
        self._intake_deps_builder = intake_deps_builder

    async def handle_incoming_email(self, payload: dict, thread_id: str | None = None) -> dict:
        trace = ["incoming_email_received"]
        deps = self._intake_deps_builder()
        graph = build_intake_graph()

        # Aquí se traduce el correo bruto al contrato de entrada que intake ya entiende.
        source_input = {
            "channel": "email",
            "subject": payload.get("subject", "") or "",
            "body": payload.get("body", "") or payload.get("body_html", "") or "",
            "from": payload.get("email_from", "") or "",
            "email_from": payload.get("email_from", "") or "",
            "sender_name": payload.get("sender_name", "") or "",
            "email_to": payload.get("email_to", "") or "",
            "email_cc": payload.get("email_cc", "") or "",
            "message_id": payload.get("message_id", "") or "",
            "received_date": payload.get("received_date", "") or "",
        }

        result = await graph.ainvoke(
            {"source_input": source_input},
            config={
                "configurable": {
                    "deps": deps,
                    "thread_id": thread_id or f"incoming-email-{payload.get('inbox_id', 'unknown')}",
                }
            },
        )

        # Si intake falla, Odoo marcará el correo como error y lo dejará visible para revisión.
        if result.get("error"):
            trace.append("intake_failed")
            return {
                "ok": False,
                "ticket_id": result.get("ticket_id"),
                "final_text": result.get("final_text", ""),
                "normalized_request": result.get("normalized_request", {}) or {},
                "ticket_payload": result.get("ticket_payload", {}) or {},
                "warnings": result.get("warnings", []) or [],
                "error": result["error"],
                "trace": trace,
            }

        trace.extend(
            [
                f"ticket_type_decided:{result.get('ticket_type', 'unknown')}",
                f"ticket_created:{result.get('ticket_id')}",
            ]
        )
        return {
            "ok": True,
            "ticket_id": result.get("ticket_id"),
            "final_text": result.get("final_text", ""),
            "normalized_request": result.get("normalized_request", {}) or {},
            "ticket_payload": result.get("ticket_payload", {}) or {},
            "warnings": result.get("warnings", []) or [],
            "error": None,
            "trace": trace,
        }


def build_incoming_email_orchestrator() -> IncomingEmailOrchestrator:
    return IncomingEmailOrchestrator()
