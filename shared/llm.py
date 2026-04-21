import os

from langchain_ollama import ChatOllama

from shared.config import OLLAMA_MODEL, OLLAMA_TEMPERATURE


def _parse_temperature(value: object, default: float = 0.0) -> float:
    """
    Convierte la temperatura a float tolerando valores vacíos o inválidos.
    """
    if value is None:
        return default

    normalized = str(value).strip()
    if not normalized or normalized.lower() == "none":
        return default

    try:
        return float(normalized)
    except (TypeError, ValueError):
        return default


def get_llm(model: str | None = None, temperature: float | None = None) -> ChatOllama:
    selected_model = model or os.getenv("OLLAMA_MODEL_OVERRIDE") or OLLAMA_MODEL
    default_temperature = _parse_temperature(OLLAMA_TEMPERATURE)
    selected_temperature = (
        float(temperature)
        if temperature is not None
        else _parse_temperature(
            os.getenv("OLLAMA_TEMPERATURE_OVERRIDE"),
            default=default_temperature,
        )
    )

    return ChatOllama(
        model=selected_model,
        temperature=selected_temperature,
    )
