from dataclasses import dataclass

from services.mcp_budget import MCPBudgetService
from shared.llm import get_llm
from shared.memory_store import QuoteMemoryStore


@dataclass
class BudgetDependencies:
    llm: object
    memory_store: QuoteMemoryStore
    mcp_service: MCPBudgetService


def build_dependencies(model: str | None = None) -> BudgetDependencies:
    return BudgetDependencies(
        llm=get_llm(model=model),
        memory_store=QuoteMemoryStore(),
        mcp_service=MCPBudgetService(),
    )
