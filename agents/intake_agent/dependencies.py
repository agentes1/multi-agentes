from dataclasses import dataclass

from shared.llm import get_llm


@dataclass
class IntakeDependencies:
    llm: object


def build_dependencies(model: str | None = None) -> IntakeDependencies:
    return IntakeDependencies(
        llm=get_llm(model=model),
    )
