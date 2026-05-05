from dataclasses import dataclass
from typing import Any

from agents.budget_agent.tools import BudgetAgentTools
from odoo.mcp_client import OdooMCPClient
from shared.config import MODEL_BUDGET_AGENT
from shared.llm import get_llm


@dataclass
class BudgetDependencies:
    """Dependencias comunes del agente de presupuestos."""

    llm: Any
    odoo_mcp_client: OdooMCPClient
    tools: BudgetAgentTools


def build_dependencies(model: str | None = None) -> BudgetDependencies:
    """Prepara el LLM, el cliente MCP y las tools del agente."""
    client = OdooMCPClient()
    return BudgetDependencies(
        llm=get_llm(model or MODEL_BUDGET_AGENT),
        odoo_mcp_client=client,
        tools=BudgetAgentTools(client),
    )