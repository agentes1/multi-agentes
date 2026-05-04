from __future__ import annotations


def build_ticket_text(ticket: dict) -> str:
    """Convierte un ticket de Odoo en texto para el router semántico."""
    subject = ticket.get("name") or ticket.get("subject") or ""
    body = ticket.get("description") or ticket.get("body") or ""
    sender = ticket.get("partner_email") or ticket.get("email_from") or ""
    return f"Asunto: {subject}\nRemitente: {sender}\nMensaje: {body}".strip()