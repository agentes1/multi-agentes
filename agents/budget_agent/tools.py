from __future__ import annotations

from dataclasses import dataclass

from odoo.mcp_client import OdooMCPClient


@dataclass
class BudgetAgentTools:
    mcp_client: OdooMCPClient

    def list_catalog(self) -> dict:
        return self.mcp_client.list_catalog()

    def get_product_catalog_snapshot(self, product_ids: list[int]) -> list[dict]:
        return self.mcp_client.get_product_catalog_snapshot(product_ids)

    def get_or_create_contact(self, company_name: str) -> int:
        return self.mcp_client.get_or_create_contact(company_name)

    def get_customer_profile(self, company_name: str) -> dict:
        return self.mcp_client.get_customer_profile(company_name)

    def find_sale_order_by_client_ref(self, client_order_ref: str) -> dict | None:
        return self.mcp_client.find_sale_order_by_client_ref(client_order_ref)

    def create_sale_order(self, partner_id: int, client_order_ref: str | None = None) -> int:
        return self.mcp_client.create_sale_order(
            partner_id=partner_id,
            client_order_ref=client_order_ref,
        )

    def create_sale_order_line(self, order_id: int, product_id: int, quantity: int = 1) -> int:
        return self.mcp_client.create_sale_order_line(
            order_id=order_id,
            product_id=product_id,
            quantity=quantity,
        )

    def get_sale_order(self, order_id: int) -> dict | None:
        return self.mcp_client.get_sale_order(order_id)

    def get_sale_order_lines(self, order_id: int) -> list[dict]:
        return self.mcp_client.get_sale_order_lines(order_id)

    def get_product(self, product_id: int) -> dict | None:
        return self.mcp_client.get_product(product_id)

    def find_related_products(self, product_ids: list[int], limit: int = 3) -> list[dict]:
        return self.mcp_client.find_related_products(product_ids=product_ids, limit=limit)
