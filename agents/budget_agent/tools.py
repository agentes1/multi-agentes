from __future__ import annotations

from dataclasses import dataclass

from odoo.mcp_client import OdooMCPClient


@dataclass
class BudgetAgentTools:
    """Tools de negocio que usa el agente de presupuestos."""

    mcp_client: OdooMCPClient

    def list_catalog(self) -> dict:
        """Devuelve el catálogo disponible en Odoo."""
        return self.mcp_client.list_catalog()

    def get_or_create_contact(self, company_name: str, email: str | None = None) -> int:
        """Busca el cliente en Odoo o lo crea si no existe."""
        return self.mcp_client.get_or_create_contact(company_name, email)

    def get_customer_profile(self, company_name: str) -> dict:
        """Obtiene información útil del cliente para redactar la respuesta."""
        return self.mcp_client.get_customer_profile(company_name)

    def get_product_catalog_snapshot(self, product_ids: list[int]) -> list[dict]:
        """Obtiene detalles de los productos seleccionados."""
        return self.mcp_client.get_product_catalog_snapshot(product_ids)

    def find_related_products(self, product_ids: list[int], limit: int = 3) -> list[dict]:
        """Busca productos relacionados para sugerencias comerciales."""
        return self.mcp_client.find_related_products(product_ids, limit)

    def find_sale_order_by_client_ref(self, client_order_ref: str) -> dict | None:
        """Evita duplicar presupuestos usando la referencia del ticket."""
        return self.mcp_client.find_sale_order_by_client_ref(client_order_ref)

    def create_sale_order(self, partner_id: int, client_order_ref: str | None = None) -> int:
        """Crea la cabecera del presupuesto en Odoo."""
        return self.mcp_client.create_sale_order(partner_id, client_order_ref)

    def create_sale_order_line(self, order_id: int, product_id: int, quantity: int = 1) -> int:
        """Añade una línea de producto al presupuesto."""
        return self.mcp_client.create_sale_order_line(order_id, product_id, quantity)

    def get_sale_order(self, order_id: int) -> dict | None:
        """Lee el presupuesto creado desde Odoo."""
        return self.mcp_client.get_sale_order(order_id)

    def get_sale_order_lines(self, order_id: int) -> list[dict]:
        """Lee las líneas del presupuesto."""
        return self.mcp_client.get_sale_order_lines(order_id)

    def post_message_to_ticket(self, ticket_id: int, body: str) -> bool:
        """Publica la respuesta final en el ticket de Helpdesk."""
        return self.mcp_client.post_message_to_ticket(ticket_id, body)