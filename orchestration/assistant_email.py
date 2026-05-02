"""Orquestación del flujo de correo entrante.

mail_inbox_input registra el correo en Odoo y llama al endpoint del backend.
Este orquestador adapta ese payload al formato esperado por intake_agent,
deja que intake cree el ticket y devuelve el resultado a Odoo.
"""

from agents.intake_agent.dependencies import build_dependencies as build_intake_dependencies
from agents.intake_agent.graph import build_intake_graph
from orchestration.assistant_entry import build_ticket_entry_orchestrator


class IncomingEmailOrchestrator:
    def __init__(
        self,
        intake_deps_builder=build_intake_dependencies,
        ticket_entry_orchestrator_builder=build_ticket_entry_orchestrator,
    ):
        self._intake_deps_builder = intake_deps_builder
        self._ticket_entry_orchestrator_builder = ticket_entry_orchestrator_builder

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

        # Tras converger en ticket, reutilizamos la misma orquestación de entrada
        # para obtener la respuesta final del agente, pero sin pasar por Discuss.
        ticket = {
            "id": result.get("ticket_id"),
            "name": result.get("ticket_payload", {}).get("title", payload.get("subject", "")),
            "description": result.get("ticket_payload", {}).get("description", payload.get("body", "")),
            "partner_name": source_input.get("sender_name", "") or payload.get("sender_name", ""),
            "partner_email": source_input.get("email_from", "") or payload.get("email_from", ""),
        }
        ticket_result = await self._ticket_entry_orchestrator_builder().handle_ticket_entry(
            ticket=ticket,
            thread_id=thread_id or f"incoming-email-ticket-{result.get('ticket_id', 'unknown')}",
        )

        if not ticket_result.get("ok"):
            trace.append("email_reply_generation_failed")
            return {
                "ok": False,
                "ticket_id": result.get("ticket_id"),
                "final_text": result.get("final_text", ""),
                "reply_text": "",
                "route_name": ticket_result.get("route_name"),
                "agent_name": ticket_result.get("agent_name"),
                "normalized_request": result.get("normalized_request", {}) or {},
                "ticket_payload": result.get("ticket_payload", {}) or {},
                "quote_summary": ticket_result.get("quote_summary", {}) or {},
                "warnings": result.get("warnings", []) or [],
                "error": ticket_result.get("error") or "No se pudo generar la respuesta del agente para el correo.",
                "trace": trace + ticket_result.get("trace", []),
            }

        return {
            "ok": True,
            "ticket_id": result.get("ticket_id"),
            "final_text": ticket_result.get("reply_text", "") or result.get("final_text", ""),
            "reply_text": ticket_result.get("reply_text", ""),
            "route_name": ticket_result.get("route_name"),
            "agent_name": ticket_result.get("agent_name"),
            "normalized_request": result.get("normalized_request", {}) or {},
            "ticket_payload": result.get("ticket_payload", {}) or {},
            "quote_summary": ticket_result.get("quote_summary", {}) or {},
            "warnings": result.get("warnings", []) or [],
            "error": None,
            "trace": trace + ticket_result.get("trace", []),
        }


def build_incoming_email_orchestrator() -> IncomingEmailOrchestrator:
    return IncomingEmailOrchestrator()
