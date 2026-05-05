from dataclasses import dataclass
from typing import Any
from shared.config import MODEL_GENERAL_AGENT
from shared.llm import get_llm

@dataclass
class GeneralDependencies:
    """Dependencias del agente general."""
    llm: Any

def build_dependencies(model: str | None = None) -> GeneralDependencies:
    """Prepara el LLM del agente."""
    return GeneralDependencies(llm=get_llm(model or MODEL_GENERAL_AGENT))