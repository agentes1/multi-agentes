from dataclasses import dataclass

from agents.budget_agent.tools import BudgetAgentTools
from odoo.mcp_client import OdooMCPClient
from shared.config import MODEL_BUDGET_AGENT
from shared.llm import get_llm


@dataclass
class BudgetDependencies:
    """Dependencias del agente de presupuestos."""
    llm: object
    odoo_mcp_client: OdooMCPClient
    tools: BudgetAgentTools


def build_dependencies(model: str | None = None) -> BudgetDependencies:
    """Construye las dependencias del agente."""
    mcp_client = OdooMCPClient()

    return BudgetDependencies(
        llm=get_llm(model=model or MODEL_BUDGET_AGENT),
        odoo_mcp_client=mcp_client,
        tools=BudgetAgentTools(mcp_client=mcp_client),
    )