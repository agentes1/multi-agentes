from dataclasses import dataclass
from typing import Any
from odoo.mcp_client import OdooMCPClient
from shared.config import MODEL_INTAKE_AGENT
from shared.llm import get_llm

@dataclass
class IntakeDependencies:
    """Dependencias del agente intake."""
    llm: Any
    odoo_mcp_client: OdooMCPClient

def build_dependencies(model: str | None = None) -> IntakeDependencies:
    """Prepara el LLM y el cliente MCP."""
    return IntakeDependencies(llm=get_llm(model or MODEL_INTAKE_AGENT), odoo_mcp_client=OdooMCPClient())