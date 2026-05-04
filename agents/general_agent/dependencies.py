from dataclasses import dataclass
from typing import Any

from shared.config import MODEL_GENERAL_AGENT
from shared.llm import get_llm


@dataclass
class GeneralDependencies:
    llm: Any


def build_dependencies(model: str | None = None) -> GeneralDependencies:
    """Construye dependencias para el agente general."""
    return GeneralDependencies(
        llm=get_llm(model=model or MODEL_GENERAL_AGENT),
    )
