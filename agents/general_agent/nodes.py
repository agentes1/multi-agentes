from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from agents.general_agent.dependencies import GeneralDependencies
from agents.general_agent.state import GeneralState
from shared.prompts import GENERAL_AGENT_SYSTEM_PROMPT, GENERAL_AGENT_USER_PROMPT

FALLBACK_REPLY = "Soy un asistente virtual cuyo objetivo es ayudarte a realizar tu trabajo de forma más eficaz. Por ahora no puedo responder a esa consulta."

def get_deps(config: RunnableConfig) -> GeneralDependencies:
    """Recupera las dependencias del agente."""
    deps = config.get("configurable", {}).get("deps")
    if not deps: raise RuntimeError("GeneralDependencies no inyectadas en config")
    return deps

def build_result(reply: str, error: str | None = None) -> dict:
    """Devuelve la respuesta en el formato del estado."""
    return {"reply_text": reply, "messages": [AIMessage(content=reply)], "error": error}

async def respond_node(state: GeneralState, config: RunnableConfig) -> dict:
    """Responde con el LLM o usa fallback."""
    input_text = (state.get("input_text") or "").strip()
    if not input_text: return build_result(FALLBACK_REPLY)
    try:
        deps = get_deps(config)
        prompt = GENERAL_AGENT_USER_PROMPT.format(input_text=input_text)
        response = await deps.llm.ainvoke([SystemMessage(content=GENERAL_AGENT_SYSTEM_PROMPT), HumanMessage(content=prompt)])
        return build_result((response.content or "").strip() or FALLBACK_REPLY)
    except Exception:
        return build_result(FALLBACK_REPLY)

async def error_node(state: GeneralState) -> dict:
    """Responde de forma controlada si algo falla."""
    return build_result(FALLBACK_REPLY)