import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from odoo.helpers import Table
from .state import TicketAgentState
from .dependencies import TicketAgentDependencies


NORMALIZATION_SYSTEM_PROMPT = """
Eres un asistente que normaliza correos para crear tickets en Odoo Helpdesk.

Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura:
{
  "title": "string",
  "description": "string",
  "customer_name": "string | null",
  "customer_email": "string | null"
}

Reglas:
- "title" debe salir del asunto si existe; si no, resume el problema en una frase corta.
- "description" debe contener el contenido útil del correo, limpio y claro.
- "customer_name" debe ser null si no se puede inferir con seguridad.
- "customer_email" debe ser el email del remitente si viene informado.
- No inventes datos.
- No añadas markdown.
""".strip()


def _get_deps(config: RunnableConfig) -> TicketAgentDependencies:
    return config["configurable"]["deps"]


async def normalize_email_node(
    state: TicketAgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    deps = _get_deps(config)

    subject = state.get("email_subject", "") or ""
    body = state.get("email_body", "") or ""
    sender_email = state.get("sender_email", "") or ""
    sender_name = state.get("sender_name")

    user_prompt = f"""
Asunto: {subject}
Remitente email: {sender_email}
Remitente nombre: {sender_name}
Cuerpo:
{body}
""".strip()

    response = await deps.llm.ainvoke(
        [
            SystemMessage(content=NORMALIZATION_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
    )

    try:
        normalized = json.loads(response.content)
    except Exception as e:
        return {"error": f"No se pudo parsear el JSON del LLM: {e}"}

    # Validación mínima y explícita
    title = normalized.get("title")
    description = normalized.get("description")

    if not title or not isinstance(title, str):
        return {"error": "El LLM no devolvió un title válido"}
    if not description or not isinstance(description, str):
        return {"error": "El LLM no devolvió un description válido"}

    # Fallbacks seguros
    normalized["customer_email"] = normalized.get("customer_email") or sender_email or None
    normalized["customer_name"] = normalized.get("customer_name") or sender_name or None

    return {"normalized_ticket": normalized}


def ensure_partner_node(
    state: TicketAgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    if state.get("error"):
        return {}

    deps = _get_deps(config)
    normalized = state["normalized_ticket"]

    customer_email = normalized.get("customer_email")
    customer_name = normalized.get("customer_name") or "Cliente sin identificar"

    if not customer_email:
        # Sin email no forzamos partner; el ticket puede crearse igualmente
        return {"partner_id": None}

    existing = deps.odoo_service.get_by_value(
        Table.Contact,
        {"email": customer_email},
        fields=["id", "name", "email"],
        limit=1,
    )

    if existing:
        return {"partner_id": existing[0]["id"]}

    partner_id = deps.odoo_service.create(
        Table.Contact,
        {
            "name": customer_name,
            "email": customer_email,
            "customer_rank": 1,
        },
    )

    return {"partner_id": partner_id}


def create_ticket_node(
    state: TicketAgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    if state.get("error"):
        return {}

    deps = _get_deps(config)
    normalized = state["normalized_ticket"]

    ticket_vals = {
        "name": normalized["title"],
        "description": normalized["description"],
    }

    # Asociar team si se informa
    team_name = state.get("team_name")
    if team_name:
        team = deps.odoo_service._query(
            Table.TicketTeam,
            "search_read",
            [[("name", "=", team_name)]],
            {"fields": ["id", "name"], "limit": 1},
        )
        if team:
            ticket_vals["team_id"] = team[0]["id"]

    # Asociar partner si existe
    if state.get("partner_id"):
        ticket_vals["partner_id"] = state["partner_id"]

    # Guardar también datos directos del remitente cuando estén
    customer_email = normalized.get("customer_email")
    if customer_email:
        ticket_vals["partner_email"] = customer_email

    ticket_id = deps.odoo_service.create(Table.Ticket, ticket_vals)

    return {"ticket_id": ticket_id}