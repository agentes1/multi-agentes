from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agents.rag_agent.dependencies import RAGDependencies
from agents.rag_agent.state import RAGState

FALLBACK_REPLY = "No he encontrado tickets similares para responder a tu consulta."

RAG_SYSTEM_PROMPT = (
    "Eres un asistente de soporte técnico. "
    "Se te proporciona una consulta de un usuario y tickets resueltos anteriormente que pueden ser relevantes. "
    "Usa esa información para responder de forma clara y concisa. "
    "Si los tickets no son suficientes para responder, indícalo. "
    "No inventes soluciones que no estén en los tickets proporcionados."
)


def get_deps(config: RunnableConfig) -> RAGDependencies:
    """Recupera las dependencias del agente."""
    deps = config.get("configurable", {}).get("deps")
    if not deps:
        raise RuntimeError("RAGDependencies no inyectadas en config")
    return deps


def ticket_to_text(ticket: dict) -> str:
    """Convierte un ticket en texto legible."""
    return (
        f"Ticket #{ticket.get('id')}\n"
        f"Título: {ticket.get('title')}\n"
        f"Descripción: {ticket.get('description')}\n"
        f"Resolución: {ticket.get('resolution')}\n"
    )


def find_similar_tickets(input_text: str, tickets: list[dict], top_k: int = 2) -> list[dict]:
    """Busca tickets similares por palabras clave."""
    input_lower = input_text.lower()
    scored = []
    for ticket in tickets:
        text = f"{ticket.get('title', '')} {ticket.get('description', '')}".lower()
        score = sum(1 for word in input_lower.split() if word in text)
        if score > 0:
            scored.append((score, ticket))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in scored[:top_k]]


async def retrieve_node(state: RAGState, config: RunnableConfig) -> dict:
    """Recupera los tickets más similares a la consulta."""
    input_text = (state.get("input_text") or "").strip()
    if not input_text:
        return {"retrieved_tickets": [], "error": "No hay texto de entrada"}
    deps = get_deps(config)
    similar = find_similar_tickets(input_text, deps.tickets)
    return {"retrieved_tickets": similar}


async def respond_node(state: RAGState, config: RunnableConfig) -> dict:
    """Genera la respuesta usando los tickets recuperados."""
    input_text = (state.get("input_text") or "").strip()
    retrieved = state.get("retrieved_tickets") or []

    if not retrieved:
        return {
            "reply_text": FALLBACK_REPLY,
            "messages": [AIMessage(content=FALLBACK_REPLY)],
        }

    context = "\n\n".join(ticket_to_text(t) for t in retrieved)
    user_prompt = (
        f"Consulta del usuario: {input_text}\n\n"
        f"Tickets resueltos relevantes:\n{context}\n\n"
        "Responde basándote en los tickets anteriores."
    )

    try:
        deps = get_deps(config)
        response = await deps.llm.ainvoke([
            SystemMessage(content=RAG_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        reply = (response.content or "").strip() or FALLBACK_REPLY
    except Exception:
        reply = FALLBACK_REPLY

    return {
        "reply_text": reply,
        "messages": [AIMessage(content=reply)],
    }


async def error_node(state: RAGState) -> dict:
    """Maneja errores del agente."""
    return {
        "reply_text": FALLBACK_REPLY,
        "messages": [AIMessage(content=FALLBACK_REPLY)],
    }