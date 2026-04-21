import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from odoo.tools import build_odoo_tools
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

    title = normalized.get("title")
    description = normalized.get("description")

    if not title or not isinstance(title, str):
        return {"error": "El LLM no devolvió un title válido"}
    if not description or not isinstance(description, str):
        return {"error": "El LLM no devolvió un description válido"}

    normalized["customer_email"] = normalized.get("customer_email") or sender_email or None
    normalized["customer_name"] = normalized.get("customer_name") or sender_name or None

    return {"normalized_ticket": normalized}


async def _run_tool_calls(response, tools: list) -> list[ToolMessage]:
    tool_map = {t.name: t for t in tools}
    results = []
    for tc in getattr(response, "tool_calls", []):
        tool = tool_map.get(tc["name"])
        if tool:
            try:
                output = tool.invoke(tc["args"])
                results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
            except Exception as e:
                results.append(ToolMessage(content=f"Error: {e}", tool_call_id=tc["id"]))
    return results


# TOOL-CALLING: el LLM consulta Odoo para enriquecer el contexto del ticket.
# Solo lectura — los errores son silenciosos para no bloquear el flujo principal.
# Las mutaciones (crear partner, crear ticket) ocurren en los nodos siguientes.
async def enrich_context_node(
    state: TicketAgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    if state.get("error"):
        return {}

    deps = _get_deps(config)
    tools = build_odoo_tools(deps.odoo_service)
    llm_with_tools = deps.llm.bind_tools(tools)

    normalized = state.get("normalized_ticket", {})
    customer_name = normalized.get("customer_name") or ""
    customer_email = normalized.get("customer_email") or ""

    prompt = (
        f"Consulta si el cliente existe en Odoo y obtén su historial. "
        f"Nombre: '{customer_name}', email: '{customer_email}'."
    )

    try:
        response = await llm_with_tools.ainvoke([HumanMessage(content=prompt)])
        tool_messages = await _run_tool_calls(response, tools)
        return {"odoo_context": {"raw_results": [m.content for m in tool_messages]}}
    except Exception:
        return {"odoo_context": {}}


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
        return {"partner_id": None}

    partner_id = deps.odoo_service.get_or_create_contact(customer_name)
    return {"partner_id": partner_id}


def create_ticket_node(
    state: TicketAgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    if state.get("error"):
        return {}

    deps = _get_deps(config)
    normalized = state["normalized_ticket"]

    ticket_id = deps.odoo_service.create_helpdesk_ticket(
        name=normalized["title"],
        description=normalized["description"],
        partner_id=state.get("partner_id"),
        partner_email=normalized.get("customer_email"),
    )

    return {"ticket_id": ticket_id}
