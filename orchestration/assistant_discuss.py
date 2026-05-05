from __future__ import annotations

import re, unicodedata
from dataclasses import dataclass

from agents.assistant_chat_agent.service import ASSISTANT_CHAT_AGENT_NAME
from agents.sales_agent.service import SALES_AGENT_NAME, build_sales_discuss_reply
from routing.semantic_router import router

AFFIRMATIVE = {"si", "sí", "ok", "vale", "adelante", "confirmo", "correcto", "de acuerdo", "hazlo", "crealo", "créalo", "generalo", "genéralo", "preparalo", "prepáralo", "genial"}
NEGATIVE_PREFIXES = ("no", "espera", "cancel", "todavia no", "todavía no", "aun no", "aún no")
BUDGET_TERMS = {"presupuesto", "cotizacion", "cotización", "budget", "quote", "oferta", "precio", "coste", "costo", "propuesta"}
SALES_TERMS = {"ventas", "venta", "comercial", "pipeline", "lead", "leads", "oportunidad", "oportunidades", "crm comercial"}
CREATE_TERMS = {"crea", "crear", "crealo", "genera", "generar", "generalo", "prepara", "preparar", "preparalo"}
CONFIRM_PROMPTS = {"quieres que", "quiere que", "confirmar", "si es correcto", "dime si", "adelante"}
CREATE_ACTIONS = {"prepar", "gener", "crear", "marcare", "ready for next stage", "presupuesto", "cotizacion", "oportunidad", "crm", "comercial"}
CLOSED_TERMS = {"he creado el presupuesto", "he creado la oportunidad", "presupuesto creado", "oportunidad comercial creada"}


@dataclass(frozen=True)
class DiscussMessageOrchestrator:
    """Orquesta los mensajes posteriores dentro de Discuss."""

    async def handle_discuss_message(self, payload: dict, thread_id: str | None = None, model: str | None = None) -> dict:
        """Mantiene la ruta activa y responde sin cambiar ventas a presupuesto."""
        trace, actions = ["discuss_message_received"], []
        route = resolve_route(payload)
        trace.append(f"route_decided:{route}")
        reply_route = route

        if is_business_confirmation(payload, route):
            route = "budget" if has_budget_context(payload, route) and not has_sales_context(payload, route) else "sales"
            reply_route = f"{route}_confirmed"
            actions.append({"type": "mark_ticket_ready", "ticket_id": payload.get("ticket_id")})
            trace.append(f"{route}_creation_confirmed")

        return build_response(route, build_reply(payload, reply_route), trace + ["response_built:discuss_orchestrator"], actions)


def resolve_route(payload: dict) -> str:
    """Usa la ruta guardada si el mensaje nuevo es corto o ambiguo."""
    saved, body = norm(payload.get("assistant_route_name")), norm(payload.get("body"))
    routed = router(build_discuss_text(payload)).name

    if saved in {"budget", "sales"} and is_ambiguous(body):
        return saved
    if saved == "sales" and routed == "budget" and not explicit_budget(body):
        return "sales"
    if routed != "discard":
        return routed
    if recent_cycle_closed(payload):
        return routed
    if saved in {"budget", "sales"}:
        return saved
    if has_sales_context(payload, routed):
        return "sales"
    if has_budget_context(payload, routed):
        return "budget"
    return routed


def build_discuss_text(payload: dict) -> str:
    """Texto mínimo que ve el router."""
    return f"Autor: {payload.get('author_email', '')}\nMensaje discuss: {payload.get('body', '')}".strip()


def build_response(route: str, reply: str, trace: list[str], actions: list[dict] | None = None) -> dict:
    """Respuesta estable para la API."""
    return {"ok": True, "route_name": route, "agent_name": SALES_AGENT_NAME if route == "sales" else ASSISTANT_CHAT_AGENT_NAME, "reply_text": reply, "normalized_request": {}, "quote_summary": {}, "actions": actions or [], "trace": trace}


def build_reply(payload: dict, route: str) -> str:
    """Construye la respuesta según la ruta activa."""
    if route == "budget_confirmed":
        return "Perfecto, marco el ticket como listo para generar el presupuesto."
    if route == "sales_confirmed":
        return "Perfecto, marco el ticket como listo para crear la oportunidad comercial en CRM."
    if route == "sales":
        return build_sales_discuss_reply(payload)
    if route == "budget":
        context = summarize_budget_context(payload)
        return f"He entendido esta solicitud de presupuesto con este contexto inicial: {context}. Si quieres que siga adelante, respóndeme con 'sí' o 'adelante'." if context else "Parece una solicitud de presupuesto. Indícame alcance, módulos o necesidades principales."
    body = norm(payload.get("body"))
    if len(body.split()) <= 2:
        return "Necesito un poco más de detalle para ayudarte. Dime si hablamos de soporte, ventas o presupuesto."
    return "Necesito un poco más de contexto para orientarte bien. Describe la necesidad y te derivo al flujo adecuado."


def is_business_confirmation(payload: dict, route: str) -> bool:
    """Detecta confirmaciones para crear presupuesto u oportunidad."""
    body = norm(payload.get("body"))
    return bool(
        payload.get("ticket_id")
        and body
        and not body.startswith(NEGATIVE_PREFIXES)
        and is_affirmative(body)
        and (has_budget_context(payload, route) or has_sales_context(payload, route))
        and (has_creation_intent(body) or recent_assistant_asked_creation(payload))
    )


def is_affirmative(text: str) -> bool:
    """Comprueba si el usuario confirma."""
    words = set(text.replace(",", " ").replace(".", " ").split())
    return text in {norm(x) for x in AFFIRMATIVE} or bool(words & {norm(x) for x in AFFIRMATIVE})


def is_ambiguous(body: str) -> bool:
    """Detecta respuestas cortas que dependen del contexto."""
    return not body or len(body.split()) <= 3 or is_affirmative(body)


def explicit_budget(body: str) -> bool:
    """Solo cambia a budget si el usuario lo pide claro."""
    return any(norm(term) in body for term in BUDGET_TERMS)


def has_creation_intent(text: str) -> bool:
    """Detecta intención de crear el registro."""
    return any(term in text for term in CREATE_TERMS)


def has_budget_context(payload: dict, route: str) -> bool:
    """Busca contexto real de presupuesto."""
    return route == "budget" or any(norm(term) in context_text(payload) for term in BUDGET_TERMS)


def has_sales_context(payload: dict, route: str) -> bool:
    """Busca contexto real de ventas."""
    return route == "sales" or any(norm(term) in context_text(payload) for term in SALES_TERMS)


def context_text(payload: dict) -> str:
    """Une ticket y mensajes recientes sin perder contexto."""
    parts = [payload.get(k, "") for k in ("ticket_title", "ticket_description", "ticket_team", "ticket_category", "ticket_type", "assistant_route_name")]
    parts += [str(m.get("body", "")) for m in payload.get("recent_messages", []) or []]
    return norm(" ".join(parts))


def recent_assistant_asked_creation(payload: dict) -> bool:
    """Revisa si el asistente pidió confirmar creación."""
    for msg in reversed(payload.get("recent_messages", []) or []):
        author, body = norm(msg.get("author_name") or msg.get("author_email")), norm(msg.get("body"))
        if ("asistente" in author or "assistant" in author) and any(t in body for t in CONFIRM_PROMPTS) and any(t in body for t in CREATE_ACTIONS):
            return True
    return False


def recent_cycle_closed(payload: dict) -> bool:
    """Evita reabrir un flujo recién cerrado."""
    for msg in reversed(payload.get("recent_messages", []) or []):
        author, body = norm(msg.get("author_name") or msg.get("author_email")), norm(msg.get("body"))
        if ("asistente" in author or "assistant" in author) and any(t in body for t in CLOSED_TERMS):
            return True
    return False


def summarize_budget_context(payload: dict) -> str:
    """Resume el contexto que se mostrará al usuario."""
    text = " ".join(plain(payload.get(k, "")) for k in ("ticket_title", "ticket_description", "body"))
    return " ".join(text.split())[:220]


def plain(value: object) -> str:
    """Quita HTML básico."""
    return " ".join(re.sub(r"<[^>]+>", " ", str(value or "")).split())


def norm(value: object) -> str:
    """Normaliza texto para comparar."""
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def build_discuss_message_orchestrator() -> DiscussMessageOrchestrator:
    """Crea el orquestador de Discuss."""
    return DiscussMessageOrchestrator()