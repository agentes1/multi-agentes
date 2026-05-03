from dataclasses import dataclass

from odoo.mcp_client import OdooMCPClient
from shared.llm import get_llm


@dataclass
class IntakeDependencies:
    """Dependencias que usa el agente de intake."""
    llm: object
    odoo_mcp_client: OdooMCPClient


def build_dependencies(model: str | None = None) -> IntakeDependencies:
    """Construye las dependencias del agente."""
    return IntakeDependencies(
        llm=get_llm(model=model),
        odoo_mcp_client=OdooMCPClient(),
    )