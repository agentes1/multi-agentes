from dataclasses import dataclass

from odoo.mcp_client import OdooMCPClient
from shared.config import MODEL_SALES_AGENT
from shared.llm import get_llm


@dataclass
class SalesDependencies:
    """Dependencias del agente de ventas."""

    llm: object
    odoo_mcp_client: OdooMCPClient


def build_dependencies(model: str | None = None) -> SalesDependencies:
    mcp_client = OdooMCPClient()
    return SalesDependencies(
        llm=get_llm(model=model or MODEL_SALES_AGENT),
        odoo_mcp_client=mcp_client,
    )
