import os

from langchain_ollama import ChatOllama

from shared.config import OLLAMA_MODEL, OLLAMA_TEMPERATURE, OLLAMA_BASE_URL


def get_llm(model: str | None = None, temperature: int | None = None) -> ChatOllama:
    selected_model = model or os.getenv("OLLAMA_MODEL_OVERRIDE") or OLLAMA_MODEL
    selected_temperature = (
        temperature
        if temperature is not None
        else float(os.getenv("OLLAMA_TEMPERATURE_OVERRIDE", str(OLLAMA_TEMPERATURE)))
    )

    return ChatOllama(
        model=selected_model,
        temperature=selected_temperature,
        base_url=OLLAMA_BASE_URL

    )
