from dataclasses import dataclass
from odoo.mcp_client import OdooMCPClient

@dataclass
class BudgetAgentTools:
    """Acciones de Odoo que usa el agente de presupuestos."""
    mcp: OdooMCPClient

    def list_catalog(self) -> dict:
        """Lee el catálogo disponible."""
        return self.mcp.list_catalog()

    def get_or_create_contact(self, company_name: str, email: str | None = None) -> int:
        """Busca o crea el cliente."""
        return self.mcp.get_or_create_contact(company_name, email)

    def find_sale_order_by_client_ref(self, client_ref: str) -> dict | None:
        """Busca un presupuesto ya asociado al ticket."""
        return self.mcp.find_sale_order_by_client_ref(client_ref)

    def create_sale_order(self, partner_id: int, client_ref: str | None = None) -> int:
        """Crea la cabecera del presupuesto."""
        return self.mcp.create_sale_order(partner_id, client_ref)

    def create_sale_order_line(self, order_id: int, product_id: int, quantity: int = 1) -> int:
        """Añade un producto al presupuesto."""
        return self.mcp.create_sale_order_line(order_id, product_id, quantity)

    def get_sale_order(self, order_id: int) -> dict | None:
        """Lee el presupuesto creado."""
        return self.mcp.get_sale_order(order_id)

    def get_sale_order_lines(self, order_id: int) -> list[dict]:
        """Lee las líneas del presupuesto."""
        return self.mcp.get_sale_order_lines(order_id)

    def find_related_products(self, product_ids: list[int], limit: int = 3) -> list[dict]:
        """Busca productos relacionados."""
        return self.mcp.find_related_products(product_ids, limit)

    def post_message_to_ticket(self, ticket_id: int, body: str) -> bool:
        """Publica la respuesta en el ticket."""
        return self.mcp.post_message_to_ticket(ticket_id, body)