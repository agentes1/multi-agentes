from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from shared.llm import get_llm

ASSISTANT_CHAT_AGENT_NAME = "assistant_chat_agent"


class AssistantChatAgent:
    def __init__(self, llm=None):
        self._llm = llm or get_llm()

    async def areply(self, payload: dict, route_name: str) -> str:
        messages = [
            SystemMessage(content=_build_system_prompt(route_name)),
            HumanMessage(content=_build_user_prompt(payload, route_name)),
        ]
        response = await self._llm.ainvoke(messages)
        return str(getattr(response, "content", "") or "").strip()


def _build_system_prompt(route_name: str) -> str:
    route_instruction = {
        "budget": (
            "La intencion es presupuesto. No crees presupuestos ni prometas importes. "
            "Ayuda a concretar alcance, modulos, usuarios, plazos, integraciones y datos que falten. "
            "Si ya hay datos suficientes, confirma lo entendido y pregunta explicitamente si quiere que "
            "preparemos el presupuesto con esos datos. Si faltan datos, pide los mas importantes y aun asi "
            "ofrece avanzar con una primera version si el cliente lo confirma."
        ),
        "budget_confirmed": (
            "La intencion es presupuesto y el usuario acaba de confirmar que quiere crearlo. "
            "Responde de forma breve que marcaras el ticket como listo para que se genere el presupuesto. "
            "No inventes importes ni condiciones comerciales."
        ),
        "discard": (
            "La intencion no esta clara o es general. Responde de forma amable, pide aclaracion y "
            "orienta al usuario hacia una solicitud de soporte o presupuesto si procede."
        ),
    }.get(route_name, "Responde de forma util y pide aclaracion si falta contexto.")

    return (
        "Eres Asistente Virtual dentro de Odoo Helpdesk. Respondes en espanol, con tono claro, "
        "profesional y cercano. Usa solo el contexto proporcionado. No inventes precios, pedidos, "
        "fechas ni datos de cliente. No digas que eres un modelo de IA. Maximo 120 palabras.\n\n"
        f"{route_instruction}"
    )


def _build_user_prompt(payload: dict, route_name: str) -> str:
    context = {
        "route_name": route_name,
        "ticket": {
            "id": payload.get("ticket_id"),
            "title": payload.get("ticket_title", ""),
            "description": payload.get("ticket_description", ""),
            "partner_name": payload.get("ticket_partner_name", ""),
            "partner_email": payload.get("ticket_partner_email", ""),
            "team": payload.get("ticket_team", ""),
            "category": payload.get("ticket_category", ""),
            "type": payload.get("ticket_type", ""),
            "stage": payload.get("ticket_stage", ""),
        },
        "channel": {
            "id": payload.get("channel_id"),
            "name": payload.get("channel_name", ""),
        },
        "current_message": {
            "id": payload.get("message_id"),
            "author_name": payload.get("author_name", ""),
            "author_email": payload.get("author_email", ""),
            "body": payload.get("body", ""),
        },
        "recent_messages": payload.get("recent_messages", []) or [],
    }

    return (
        "Genera la siguiente respuesta del asistente para este chat de Helpdesk.\n"
        "Ten en cuenta el ultimo mensaje del usuario y el historial reciente.\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
