from __future__ import annotations

import re


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
        ("implantacion_odoo", ("implantacion", "implantación", "implantar odoo", "puesta en marcha")),
        ("formacion", ("formacion", "formación", "capacitacion", "capacitación")),
        ("soporte_mensual", ("soporte mensual", "mantenimiento", "acompanamiento", "acompañamiento")),
        ("desarrollo_medida", ("desarrollo a medida", "personalizacion", "personalización", "integracion", "integración")),
    )
    requirements: list[str] = []
    normalized_text = re.sub(r"\s+", " ", ticket_text.lower())
    for canonical, terms in patterns:
        if any(term in normalized_text for term in terms):
            requirements.append(canonical)
    return requirements
