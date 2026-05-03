import os

from langchain_ollama import ChatOllama

from shared.config import OLLAMA_MODEL, OLLAMA_TEMPERATURE, OLLAMA_BASE_URL


def _clean_env(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().strip("\"'")


def get_llm(model: str | None = None, temperature: int | None = None) -> ChatOllama:
    selected_model = model or _clean_env(os.getenv("OLLAMA_MODEL_OVERRIDE")) or OLLAMA_MODEL
    selected_temperature = (
        temperature
        if temperature is not None
        else int(_clean_env(os.getenv("OLLAMA_TEMPERATURE_OVERRIDE")) or str(OLLAMA_TEMPERATURE))
    )

    return ChatOllama(
        model=selected_model,
        temperature=selected_temperature,
        base_url=OLLAMA_BASE_URL

    )
