from agents.general_agent.dependencies import build_dependencies
from agents.general_agent.graph import build_general_graph

GENERAL_AGENT_NAME = "general_agent"

_FALLBACK_REPLY = (
    "Soy un asistente virtual cuyo objetivo es ayudarte a realizar tu trabajo "
    "de forma más eficaz. Por ahora no puedo responder a esa consulta."
)

GENERAL_AGENT_RESPONSE = _FALLBACK_REPLY


async def build_general_response(text: str = "", model: str | None = None) -> str:
    """Ejecuta el grafo del agente general y devuelve la respuesta al cliente.

    Si no se recibe texto, devuelve la respuesta de fallback sin llamar al LLM.
    """
    if not text:
        return _FALLBACK_REPLY

    deps = build_dependencies(model=model)
    graph = build_general_graph()
    result = await graph.ainvoke(
        {"input_text": text},
        config={"configurable": {"deps": deps}},
    )
    return result.get("reply_text") or _FALLBACK_REPLY
