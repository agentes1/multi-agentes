from dataclasses import dataclass

from agents.budget_agent.tools import BudgetAgentTools
from odoo.api import OdooAPI
from odoo.mcp_client import OdooMCPClient
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME
from shared.llm import get_llm


# dependencias externas que necesita el agente
@dataclass
class BudgetDependencies:
    llm: object
    odoo_wrapper: OdooAPI
    tools: BudgetAgentTools


def build_dependencies(model: str | None = None) -> BudgetDependencies:
    odoo_wrapper = OdooAPI(
        url=ODOO_BASE_URL,
        username=ODOO_USERNAME,
        password=ODOO_PASSWORD,
        db=ODOO_DB,
    )
    return BudgetDependencies(
        llm=get_llm(model=model),
        odoo_wrapper=odoo_wrapper,
        tools=BudgetAgentTools(mcp_client=OdooMCPClient()),
    )
