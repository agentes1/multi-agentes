from langchain_ollama import ChatOllama

from shared.config import OLLAMA_MODEL, OLLAMA_TEMPERATURE


def get_llm() -> ChatOllama:
    return ChatOllama(
        model=OLLAMA_MODEL,
        temperature=OLLAMA_TEMPERATURE,
    )
