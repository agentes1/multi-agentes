from __future__ import annotations


def build_ticket_text(ticket: dict) -> str:
    subject = ticket.get("name", ticket.get("subject", ""))
    body = ticket.get("description", ticket.get("body", ""))
    sender = ticket.get("partner_email", ticket.get("email_from", ""))
    return f"Asunto: {subject}\nRemitente: {sender}\nMensaje: {body}".strip()
