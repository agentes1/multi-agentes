from __future__ import annotations

from odoo import odoo_mcp_server


class OdooMCPClient:
    """Adaptador local para consumir las tools del MCP de Odoo desde los agentes.

    En esta fase se invocan en proceso, pero el contrato queda aislado para poder
    sustituirlo por un cliente MCP remoto más adelante sin tocar los agentes.
    """

    def list_catalog(self) -> dict:
        return odoo_mcp_server.list_catalog()

    def find_company(self, name: str, exact: bool = False, limit: int = 5) -> list[dict]:
        return odoo_mcp_server.find_company(name=name, exact=exact, limit=limit)

    def get_product_catalog_snapshot(self, product_ids: list[int]) -> list[dict]:
        return odoo_mcp_server.get_product_catalog_snapshot(product_ids=product_ids)

    def find_products_by_text(self, text: str, limit: int = 5) -> list[dict]:
        return odoo_mcp_server.find_products_by_text(text=text, limit=limit)

    def get_product(self, product_id: int) -> dict | None:
        return odoo_mcp_server.get_product(product_id=product_id)

    def get_or_create_contact(self, company_name: str) -> int:
        return odoo_mcp_server.get_or_create_contact(company_name=company_name)

    def get_customer_profile(self, company_name: str) -> dict:
        return odoo_mcp_server.get_customer_profile(company_name=company_name)

    def get_customer_history(self, partner_id: int, limit: int = 10) -> dict:
        return odoo_mcp_server.get_customer_history(partner_id=partner_id, limit=limit)

    def find_sale_order_by_client_ref(self, client_order_ref: str) -> dict | None:
        return odoo_mcp_server.find_sale_order_by_client_ref(client_order_ref=client_order_ref)

    def create_sale_order(self, partner_id: int, client_order_ref: str | None = None) -> int:
        return odoo_mcp_server.create_sale_order(
            partner_id=partner_id,
            client_order_ref=client_order_ref,
        )

    def create_sale_order_line(self, order_id: int, product_id: int, quantity: int = 1) -> int:
        return odoo_mcp_server.create_sale_order_line(
            order_id=order_id,
            product_id=product_id,
            quantity=quantity,
        )

    def get_sale_order(self, order_id: int) -> dict | None:
        return odoo_mcp_server.get_sale_order(order_id=order_id)

    def get_sale_order_lines(self, order_id: int) -> list[dict]:
        return odoo_mcp_server.get_sale_order_lines(order_id=order_id)

    def find_related_products(self, product_ids: list[int], limit: int = 3) -> list[dict]:
        return odoo_mcp_server.find_related_products(product_ids=product_ids, limit=limit)
