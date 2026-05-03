from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import unicodedata

from agents.assistant_chat_agent.service import ASSISTANT_CHAT_AGENT_NAME, AssistantChatAgent
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
_CREATION_TERMS = ("crea", "crear", "crealo", "genera", "generar", "generalo", "prepara", "preparar", "preparalo")
_ASSISTANT_CONFIRMATION_PROMPT_TERMS = (
    "quieres que",
    "quiere que",
    "podrias confirmar",
    "puedes confirmar",
    "confirmar si es correcto",
    "si es asi",
    "si es correcto",
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
)


@dataclass(frozen=True)
class DiscussMessageOrchestrator:
    """Orquesta mensajes posteriores dentro de Discuss."""

    chat_agent_builder: Callable[..., AssistantChatAgent] = AssistantChatAgent

    async def handle_discuss_message(self, payload: dict, thread_id: str | None = None, model: str | None = None) -> dict:
        """Enruta el mensaje y pide respuesta al agente de chat."""
        trace = ["discuss_message_received"]
        route_name = router(build_discuss_text(payload)).name
        trace.append(f"route_decided:{route_name}")
        agent_route_name = route_name
        actions = []

        if is_budget_creation_confirmation(payload, route_name):
            route_name = "budget"
            agent_route_name = "budget_confirmed"
            actions.append({"type": "mark_ticket_ready", "ticket_id": payload.get("ticket_id")})
            trace.append("budget_creation_confirmed")

        chat_agent = self.chat_agent_builder()
        reply_text = await chat_agent.areply(payload=payload, route_name=agent_route_name)

        if not reply_text:
            return build_discuss_response(route_name, "", trace + ["assistant_chat_empty_reply"], actions=actions)

        return build_discuss_response(
            route_name,
            reply_text,
            trace + [f"agent_completed:{ASSISTANT_CHAT_AGENT_NAME}"],
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
        "agent_name": ASSISTANT_CHAT_AGENT_NAME,
        "reply_text": reply_text,
        "normalized_request": {},
        "quote_summary": {},
        "actions": actions or [],
        "trace": trace,
    }


def is_budget_creation_confirmation(payload: dict, route_name: str) -> bool:
    """Detecta si el usuario confirma que quiere generar el presupuesto."""
    if not payload.get("ticket_id"):
        return False

    body = _normalize(payload.get("body", ""))
    if not body or body.startswith(_NEGATIVE_PREFIXES):
        return False
    if not _is_affirmative(body):
        return False
    if not _has_budget_context(payload, route_name):
        return False

    return _has_creation_intent(body) or _recent_assistant_asked_to_create_budget(payload)


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


def _has_creation_intent(text: str) -> bool:
    return any(term in text for term in _CREATION_TERMS)


def _recent_assistant_asked_to_create_budget(payload: dict) -> bool:
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
    return text


def build_discuss_message_orchestrator() -> DiscussMessageOrchestrator:
    """Crea el orquestador de Discuss."""
    return DiscussMessageOrchestrator()
