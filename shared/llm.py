from langchain_ollama import ChatOllama

from shared.config import OLLAMA_MODEL, OLLAMA_TEMPERATURE


def get_llm(model: str = OLLAMA_MODEL, temperature: int = OLLAMA_TEMPERATURE) -> ChatOllama:
    return ChatOllama(
        model=model,
        temperature=temperature,
    )
