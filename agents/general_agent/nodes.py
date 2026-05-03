from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agents.general_agent.dependencies import GeneralDependencies
from agents.general_agent.state import GeneralState
from shared.prompts import GENERAL_AGENT_SYSTEM_PROMPT, GENERAL_AGENT_USER_PROMPT

_FALLBACK_REPLY = (
    "Soy un asistente virtual cuyo objetivo es ayudarte a realizar tu trabajo "
    "de forma más eficaz. Por ahora no puedo responder a esa consulta."
)


def _get_deps(config: RunnableConfig) -> GeneralDependencies:
    deps = config.get("configurable", {}).get("deps")
    if deps is None:
        raise RuntimeError("GeneralDependencies no inyectadas en config")
    return deps


async def respond_node(state: GeneralState, config: RunnableConfig) -> dict:
    """Genera una respuesta usando el LLM o devuelve el fallback estático."""
    deps = _get_deps(config)
    input_text = (state.get("input_text") or "").strip()

    if not input_text:
        return {
            "reply_text": _FALLBACK_REPLY,
            "messages": [AIMessage(content=_FALLBACK_REPLY)],
            "error": None,
        }

    try:
        prompt = GENERAL_AGENT_USER_PROMPT.format(input_text=input_text)
        response = await deps.llm.ainvoke(
            [
                SystemMessage(content=GENERAL_AGENT_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
        reply_text = (response.content or "").strip() or _FALLBACK_REPLY
    except Exception:
        reply_text = _FALLBACK_REPLY

    return {
        "reply_text": reply_text,
        "messages": [AIMessage(content=reply_text)],
        "error": None,
    }


async def error_node(state: GeneralState) -> dict:
    """Devuelve un error controlado cuando el flujo no puede continuar."""
    return {
        "reply_text": _FALLBACK_REPLY,
        "messages": [AIMessage(content=_FALLBACK_REPLY)],
    }
