from agents.general_agent.dependencies import build_dependencies
from agents.general_agent.graph import build_general_graph
from agents.general_agent.nodes import FALLBACK_REPLY

GENERAL_AGENT_NAME = "general_agent"
GENERAL_AGENT_RESPONSE = FALLBACK_REPLY

async def build_general_response(text: str = "", model: str | None = None) -> str:
    """Ejecuta el agente general y devuelve solo el texto."""
    if not text.strip(): return FALLBACK_REPLY
    graph = build_general_graph()
    result = await graph.ainvoke({"input_text": text}, config={"configurable": {"deps": build_dependencies(model)}})
    return result.get("reply_text") or FALLBACK_REPLY