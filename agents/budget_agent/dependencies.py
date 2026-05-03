from dataclasses import dataclass
from typing import Any

from agents.budget_agent.tools import BudgetAgentTools
from odoo.api_wrapper import OdooAPIWrapper
from odoo.mcp_client import OdooMCPClient
from shared.config import MODEL_BUDGET_AGENT, ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME
from shared.llm import get_llm


@dataclass
class BudgetDependencies:
    llm: Any
    odoo_wrapper: OdooAPIWrapper
    tools: BudgetAgentTools


def build_dependencies(model: str | None = None) -> BudgetDependencies:
    """Construye dependencias para el agente de presupuesto."""
    wrapper = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)
    return BudgetDependencies(
        llm=get_llm(model=model or MODEL_BUDGET_AGENT),
        odoo_wrapper=wrapper,
        tools=BudgetAgentTools(mcp_client=OdooMCPClient()),
    )
