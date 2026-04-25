from agents.budget_agent.dependencies import build_budget_dependencies
from agents.budget_agent.graph import build_budget_graph
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


def build_budget_agent():
    graph = build_budget_graph()
    deps = build_budget_dependencies()
    return graph, deps


async def run_ticket_pipeline(
    email_subject: str,
    email_body: str,
    sender_email: str,
    sender_name: str | None = None,
    team_name: str | None = None,
) -> dict:
    """Ejecuta solo el agente de tickets."""
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


async def run_budget_pipeline_from_ticket(ticket_result: dict) -> dict:
    """Ejecuta el agente de presupuestos usando el resultado del agente de tickets."""
    if ticket_result.get("error"):
        return {
            "error": f"No se ejecuta budget_agent porque falló intake_agent: {ticket_result['error']}",
            "ticket_result": ticket_result,
        }

    ticket = ticket_result.get("ticket") or {}
    ticket_vals = ticket_result.get("ticket_vals") or {}

    graph, deps = build_budget_agent()

    initial_state = {
        "ticket": ticket,
        "ticket_title": ticket.get("title") or ticket_vals.get("name") or "",
        "ticket_description": ticket.get("description") or ticket_vals.get("description") or "",
        "company_name": ticket.get("company_name") or "",
    }

    result = await graph.ainvoke(
        initial_state,
        config={
            "configurable": {
                "deps": deps,
                "thread_id": "budget-test-thread",
            }
        },
    )

    budget = result.get("budget")
    budget_dict = _to_public_dict(budget) or {}

    catalog = deps.odoo_service.list_catalog(limit=500)

    debug = {
        "initial_state_sent_to_budget_agent": initial_state,
        "catalog_from_odoo": catalog,
        "budget_after_graph": budget_dict,
        "budget_lines_after_graph": budget_dict.get("lines", []),
        "product_ids_returned_by_llm": [
            line.get("product_id")
            for line in budget_dict.get("lines", [])
        ],
        "valid_product_ids_from_odoo": [
            product.get("id")
            for product in catalog
        ],
        "catalog_names": [
            {
                "id": product.get("id"),
                "name": product.get("name"),
                "code": product.get("default_code"),
                "price": product.get("list_price"),
            }
            for product in catalog
        ],
    }

    return {
        "error": result.get("error"),
        "budget": budget_dict,
        "sale_order_id": result.get("sale_order_id") or budget_dict.get("sale_order_id"),
        "quote_summary": result.get("quote_summary") or budget_dict,
        "debug": debug,
        "ticket_result": ticket_result,
    }


async def run_ticket_to_budget_pipeline(
    email_subject: str,
    email_body: str,
    sender_email: str,
    sender_name: str | None = None,
    team_name: str | None = None,
) -> dict:
    """Ejecuta intake_agent y después budget_agent."""
    ticket_result = await run_ticket_pipeline(
        email_subject=email_subject,
        email_body=email_body,
        sender_email=sender_email,
        sender_name=sender_name,
        team_name=team_name,
    )

    budget_result = await run_budget_pipeline_from_ticket(ticket_result)

    return {
        "ticket": ticket_result,
        "budget": budget_result,
        "error": ticket_result.get("error") or budget_result.get("error"),
    }


async def run_demo_ticket() -> dict:
    """Simula un correo de soporte para probar solo intake_agent."""
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


async def run_demo_budget() -> dict:
    """Simula un correo de presupuesto y prueba intake_agent + budget_agent."""
    return await run_ticket_to_budget_pipeline(
        email_subject="Solicitud de presupuesto",
        email_body=(
            "Hola,\n\n"
            "Soy Ana López de Acme SL. Necesitamos un presupuesto para 3 servicios "
            "1 de Generación de presupuestos con IA y 2 de dashboards\n"
            "Gracias."
        ),
        sender_email="ana.lopez@acme.es",
        sender_name="Ana López",
        team_name="Ventas",
    )