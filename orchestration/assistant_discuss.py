from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from agents.assistant_chat_agent.service import ASSISTANT_CHAT_AGENT_NAME
from agents.sales_agent.service import SALES_AGENT_NAME, build_sales_discuss_reply
from routing.semantic_router import router


_AFFIRMATIVE_TERMS = {
    "si",
    "sí",
    "ok",
    "vale",
    "adelante",
    "confirmo",
    "correcto",
    "de acuerdo",
    "hazlo",
    "crealo",
    "créalo",
    "generalo",
    "genéralo",
    "preparalo",
    "prepáralo",
}
_NEGATIVE_PREFIXES = ("no", "espera", "cancel", "todavia no", "todavía no", "aun no", "aún no")
_BUDGET_TERMS = ("presupuesto", "cotizacion", "cotización", "budget", "quote", "oferta")
_SALES_TERMS = ("ventas", "comercial", "pipeline", "lead", "leads", "oportunidades", "crm comercial")
_CREATION_TERMS = ("crea", "crear", "crealo", "genera", "generar", "generalo", "prepara", "preparar", "preparalo")
_ASSISTANT_CONFIRMATION_PROMPT_TERMS = (
    "quieres que",
    "quiere que",
    "podrias confirmar",
    "puedes confirmar",
    "confirmar si es correcto",
    "si es asi",
    "si es correcto",
    "dime si",
    "dime si o adelante",
    "dime si o",
)
_ASSISTANT_CREATION_ACTION_TERMS = (
    "prepar",
    "gener",
    "crear",
    "creemos",
    "marcare",
    "ready for next stage",
    "listo",
    "presupuesto",
    "cotizacion",
    "oportunidad",
    "crm",
    "comercial",
)
_ASSISTANT_CYCLE_CLOSED_TERMS = (
    "he creado el presupuesto",
    "he creado la oportunidad",
    "presupuesto creado",
    "oportunidad comercial creada",
    "si quieres puedes indicarme una nueva necesidad",
)


@dataclass(frozen=True)
class DiscussMessageOrchestrator:
    """Orquesta mensajes posteriores dentro de Discuss."""

    async def handle_discuss_message(self, payload: dict, thread_id: str | None = None, model: str | None = None) -> dict:
        """Enruta el mensaje y devuelve una respuesta controlada desde la orquestación."""
        trace = ["discuss_message_received"]
        route_name = router(build_discuss_text(payload)).name
        trace.append(f"route_decided:{route_name}")
        contextual_route = _promote_context_route(payload, route_name)
        if contextual_route != route_name:
            trace.append(f"context_route_promoted:{contextual_route}")
            route_name = contextual_route
        actions = []
        reply_route_name = route_name

        if is_business_creation_confirmation(payload, route_name):
            route_name = "budget" if _has_budget_context(payload, route_name) else "sales"
            reply_route_name = "budget_confirmed" if route_name == "budget" else "sales_confirmed"
            actions.append({"type": "mark_ticket_ready", "ticket_id": payload.get("ticket_id")})
            trace.append(f"{route_name}_creation_confirmed")

        reply_text = _build_discuss_reply(payload=payload, route_name=reply_route_name)

        return build_discuss_response(
            route_name,
            reply_text,
            trace + ["response_built:discuss_orchestrator"],
            actions=actions,
        )


def build_discuss_text(payload: dict) -> str:
    """Convierte el mensaje de Discuss en texto enrutable."""
    return f"Autor: {payload.get('author_email', '')}\nMensaje discuss: {payload.get('body', '')}".strip()


def build_discuss_response(route_name: str, reply_text: str, trace: list[str], actions: list[dict] | None = None) -> dict:
    """Construye una respuesta estable para la API."""
    return {
        "ok": True,
        "route_name": route_name,
        "agent_name": SALES_AGENT_NAME if route_name == "sales" else ASSISTANT_CHAT_AGENT_NAME,
        "reply_text": reply_text,
        "normalized_request": {},
        "quote_summary": {},
        "actions": actions or [],
        "trace": trace,
    }


def _build_discuss_reply(payload: dict, route_name: str) -> str:
    if route_name == "budget_confirmed":
        return "Perfecto, marco el ticket como listo para la siguiente fase para generar el presupuesto."

    if route_name == "sales_confirmed":
        return "Perfecto, marco el ticket como listo para la siguiente fase para crear la oportunidad comercial en CRM."

    if route_name == "budget":
        requirements = _summarize_budget_context(payload)
        if requirements:
            return (
                f"He entendido esta solicitud de presupuesto con este contexto inicial: {requirements}. "
                "Si quieres que siga adelante, respóndeme con 'sí' o 'adelante' y lo marcaré como "
                "'Ready for next stage' para preparar el presupuesto."
            )
        return (
            "Parece una solicitud de presupuesto. Antes de prepararlo, indícame el alcance, módulos, "
            "usuarios o necesidades principales. Cuando esté correcto, dime 'sí' o 'adelante' y lo marcaré "
            "como 'Ready for next stage'."
        )

    if route_name == "sales":
        return build_sales_discuss_reply(payload)

    body = _normalize(payload.get("body", ""))
    if any(term in body for term in {"hola", "buenas", "buenos dias", "buen dia", "que tal", "que tiempo"}):
        return (
            "Hola. Para orientarte bien, cuéntame un poco más. Si buscas un presupuesto, dime qué módulos o alcance "
            "quieres valorar."
        )
    if len(body.split()) <= 2:
        return (
            "Necesito un poco más de detalle para ayudarte. Si buscas un presupuesto, dime qué área, módulos o "
            "necesidades quieres valorar."
        )
    return (
        "Necesito un poco más de contexto para orientarte bien. Si buscas un presupuesto, dime qué módulos o alcance "
        "quieres valorar; si es un problema, descríbeme el error y los pasos para reproducirlo."
    )


def is_business_creation_confirmation(payload: dict, route_name: str) -> bool:
    """Detecta si el usuario confirma que quiere crear el registro de negocio asociado."""
    if not payload.get("ticket_id"):
        return False

    body = _normalize(payload.get("body", ""))
    if not body or body.startswith(_NEGATIVE_PREFIXES):
        return False
    if not _is_affirmative(body):
        return False
    if not (_has_budget_context(payload, route_name) or _has_sales_context(payload, route_name)):
        return False

    return _has_creation_intent(body) or _recent_assistant_asked_to_create_business_record(payload)


def _is_affirmative(text: str) -> bool:
    words = set(text.replace(",", " ").replace(".", " ").split())
    return text in _AFFIRMATIVE_TERMS or bool(words.intersection(_normalize(term) for term in _AFFIRMATIVE_TERMS))


def _has_budget_context(payload: dict, route_name: str) -> bool:
    if route_name == "budget":
        return True
    context_parts = [
        payload.get("ticket_title", ""),
        payload.get("ticket_description", ""),
        payload.get("ticket_team", ""),
        payload.get("ticket_category", ""),
        payload.get("ticket_type", ""),
    ]
    context_parts.extend(str(message.get("body", "")) for message in payload.get("recent_messages", []) or [])
    context = _normalize(" ".join(context_parts))
    return any(_normalize(term) in context for term in _BUDGET_TERMS)


def _has_sales_context(payload: dict, route_name: str) -> bool:
    if route_name == "sales":
        return True
    context_parts = [
        payload.get("ticket_title", ""),
        payload.get("ticket_description", ""),
        payload.get("ticket_team", ""),
        payload.get("ticket_category", ""),
        payload.get("ticket_type", ""),
    ]
    context_parts.extend(str(message.get("body", "")) for message in payload.get("recent_messages", []) or [])
    context = _normalize(" ".join(context_parts))
    return any(_normalize(term) in context for term in _SALES_TERMS)


def _has_creation_intent(text: str) -> bool:
    return any(term in text for term in _CREATION_TERMS)


def _recent_assistant_asked_to_create_business_record(payload: dict) -> bool:
    for message in reversed(payload.get("recent_messages", []) or []):
        author = _normalize(message.get("author_name", "") or message.get("author_email", ""))
        body = _normalize(message.get("body", ""))
        if "asistente" not in author and "assistant" not in author:
            continue
        if any(term in body for term in _ASSISTANT_CONFIRMATION_PROMPT_TERMS) and any(
            term in body for term in _ASSISTANT_CREATION_ACTION_TERMS
        ):
            return True
    return False


def _normalize(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def _summarize_budget_context(payload: dict) -> str:
    context_parts = [
        _plain_text(payload.get("ticket_title", "")),
        _plain_text(payload.get("ticket_description", "")),
        _plain_text(payload.get("body", "")),
    ]
    filtered = [part for part in context_parts if part]
    if not filtered:
        return ""
    summary = " ".join(filtered)
    return " ".join(summary.split())[:220]


def _promote_context_route(payload: dict, route_name: str) -> str:
    if route_name != "discard":
        return route_name
    body = _normalize(payload.get("body", ""))
    if any(term in body for term in {"que tiempo", "clima", "saludo"}):
        return route_name
    if _recent_assistant_closed_business_cycle(payload):
        return route_name
    if _has_budget_context(payload, route_name):
        return "budget"
    if _has_sales_context(payload, route_name):
        return "sales"
    return route_name


def _recent_assistant_closed_business_cycle(payload: dict) -> bool:
    for message in reversed(payload.get("recent_messages", []) or []):
        author = _normalize(message.get("author_name", "") or message.get("author_email", ""))
        body = _normalize(message.get("body", ""))
        if "asistente" not in author and "assistant" not in author:
            continue
        if any(term in body for term in _ASSISTANT_CYCLE_CLOSED_TERMS):
            return True
    return False


def _plain_text(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split()).strip()


def build_discuss_message_orchestrator() -> DiscussMessageOrchestrator:
    """Crea el orquestador de Discuss."""
    return DiscussMessageOrchestrator()
