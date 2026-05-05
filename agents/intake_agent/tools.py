from langchain_core.tools import tool
from agents.intake_agent.dependencies import IntakeDependencies

def build_intake_tools(deps: IntakeDependencies):
    """Construye las tools consultivas del intake."""

    @tool
    def find_company(name: str, exact: bool = False, limit: int = 5) -> list[dict]:
        """Busca empresas o contactos en Odoo."""
        return deps.odoo_mcp_client.find_company(name=name, exact=exact, limit=limit)

    @tool
    def get_customer_profile(company_name: str) -> dict:
        """Obtiene el perfil básico de un cliente."""
        return deps.odoo_mcp_client.get_customer_profile(company_name=company_name)

    @tool
    def get_customer_history(partner_id: int, limit: int = 10) -> dict:
        """Obtiene pedidos y tickets anteriores."""
        return deps.odoo_mcp_client.get_customer_history(partner_id=partner_id, limit=limit)

    return [find_company, get_customer_profile, get_customer_history]