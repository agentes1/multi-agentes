from agents.intake_agent.dependencies import build_ticket_dependencies
from agents.intake_agent.graph import build_ticket_graph


def _to_public_dict(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def build_ticket_agent():
    graph = build_ticket_graph()
    deps = build_ticket_dependencies()
    return graph, deps


async def run_ticket_pipeline(
    email_subject: str,
    email_body: str,
    sender_email: str,
    sender_name: str | None = None,
    team_name: str | None = None,
) -> dict:
    """
    Ejecuta el agente de tickets con un correo ya recibido/simulado.
    """
    graph, deps = build_ticket_agent()

    initial_state = {
        "email_subject": email_subject,
        "email_body": email_body,
        "sender_email": sender_email,
        "sender_name": sender_name,
        "team_name": team_name,
    }

    result = await graph.ainvoke(
        initial_state,
        config={
            "configurable": {
                "deps": deps,
                "thread_id": "ticket-test-thread",
            }
        },
    )
    ticket = result.get("ticket")
    ticket_dict = _to_public_dict(ticket) or {}

    return {
        "error": result.get("error"),
        "ticket": ticket_dict,
        "normalized_ticket": ticket_dict,
        "partner_id": ticket_dict.get("partner_id"),
        "company_is_new": ticket_dict.get("company_is_new", False),
        "missing_fields": ticket_dict.get("missing_fields", []),
        "ticket_vals": result.get("ticket_vals", {}),
        "ticket_id": result.get("ticket_id"),
    }


async def run_demo_ticket() -> dict:
    """
    Simula un correo de entrada para comprobar que todo funciona.
    """
    return await run_ticket_pipeline(
        email_subject="No puedo acceder al portal de clientes",
        email_body=(
            "Hola,\n\n"
            "Soy Ana López de Acme SL. Desde esta mañana no puedo iniciar sesión "
            "en el portal. Me indica credenciales incorrectas aunque estoy usando "
            "la misma contraseña de siempre.\n\n"
            "¿Podéis revisarlo?\n\n"
            "Gracias."
        ),
        sender_email="ana.lopez@acme.es",
        sender_name="Ana López",
        team_name="Soporte cliente",
    )
