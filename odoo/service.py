from __future__ import annotations

from odoo.api import OdooAPIWrapper
from odoo.helpers import Table


class OdooService:
    """Capa de dominio sobre OdooAPIWrapper.

    Separa explícitamente consultas (expuestas como LangChain tools en odoo/tools.py)
    de mutaciones (usadas por nodos hardcodeados del grafo).
    """

    def __init__(self, wrapper: OdooAPIWrapper) -> None:
        self._wrapper = wrapper

    # ─── MUTACIONES ────────────────────────────────────────────────────────────
    # Usadas directamente por nodos del grafo. NO expuestas como tools.
    # Razón: crear registros en Odoo debe ser determinista, no delegarse al LLM.

    def find_products_by_text(self, text: str, limit: int = 5) -> list[dict]:
        domain = [("name", "ilike", text), ("active", "=", True)]
        return self._wrapper._query(
            "product.product",
            "search_read",
            [domain],
            {"fields": ["id", "name", "default_code", "list_price"], "limit": limit},
        ) or []

    def get_or_create_contact(self, company_name: str) -> int:
        existing = self._wrapper.get_by_value(
            Table.Contact,
            {"name": company_name},
            fields=["id"],
            limit=1,
        )
        if existing:
            return existing[0]["id"]
        return self._wrapper._query(
            "res.partner",
            "create",
            [{"name": company_name, "is_company": True, "customer_rank": 1}],
        )

    def create_sale_order(self, partner_id: int) -> int:
        return self._wrapper._query(
            "sale.order",
            "create",
            [{"partner_id": partner_id}],
        )

    def create_sale_order_line(
        self, order_id: int, product_id: int, quantity: int
    ) -> int:
        return self._wrapper._query(
            "sale.order.line",
            "create",
            [{
                "order_id": order_id,
                "product_id": product_id,
                "product_uom_qty": quantity,
            }],
        )

    def get_sale_order(self, sale_order_id: int) -> dict:
        results = self._wrapper._query(
            "sale.order",
            "read",
            [[sale_order_id]],
            {"fields": ["name", "partner_id", "amount_untaxed", "amount_total", "state"]},
        )
        return results[0] if results else {}

    def create_helpdesk_ticket(
        self,
        name: str,
        description: str,
        partner_id: int | None = None,
        partner_email: str | None = None,
        team_id: int | None = None,
    ) -> int:
        vals: dict = {"name": name, "description": description}
        if partner_id:
            vals["partner_id"] = partner_id
        if partner_email:
            vals["partner_email"] = partner_email
        if team_id:
            vals["team_id"] = team_id
        return self._wrapper._query("helpdesk.ticket", "create", [vals])

    # ─── CONSULTAS ─────────────────────────────────────────────────────────────
    # Expuestas como LangChain tools en odoo/tools.py.
    # Solo lectura — si fallan, no modifican nada en Odoo.

    def search_products(self, text: str, limit: int = 10) -> list[dict]:
        domain = [("name", "ilike", text), ("active", "=", True)]
        return self._wrapper._query(
            "product.product",
            "search_read",
            [domain],
            {"fields": ["id", "name", "default_code", "list_price", "type"], "limit": limit},
        ) or []

    def get_product_by_code(self, code: str) -> dict | None:
        results = self._wrapper._query(
            "product.product",
            "search_read",
            [[("default_code", "=", code), ("active", "=", True)]],
            {"fields": ["id", "name", "default_code", "list_price", "type"], "limit": 1},
        )
        return results[0] if results else None

    def list_catalog(self) -> list[dict]:
        return self._wrapper._query(
            "product.product",
            "search_read",
            [[("active", "=", True)]],
            {"fields": ["id", "name", "default_code", "list_price"], "limit": 100},
        ) or []

    def find_client(self, name: str) -> dict | None:
        results = self._wrapper._query(
            "res.partner",
            "search_read",
            [[("name", "ilike", name), ("active", "=", True)]],
            {"fields": ["id", "name", "email", "phone", "is_company"], "limit": 1},
        )
        return results[0] if results else None

    def get_client_history(self, partner_id: int) -> dict:
        return {
            "orders": self.list_client_orders(partner_id),
            "tickets": self.list_client_tickets(partner_id),
        }

    def get_order(self, order_id: int) -> dict:
        results = self._wrapper._query(
            "sale.order",
            "read",
            [[order_id]],
            {"fields": ["name", "state", "amount_untaxed", "amount_total", "date_order"]},
        )
        return results[0] if results else {}

    def list_client_orders(self, partner_id: int, limit: int = 10) -> list[dict]:
        return self._wrapper._query(
            "sale.order",
            "search_read",
            [[("partner_id", "=", partner_id)]],
            {
                "fields": ["id", "name", "state", "amount_total", "date_order"],
                "limit": limit,
                "order": "date_order desc",
            },
        ) or []

    def get_ticket(self, ticket_id: int) -> dict:
        results = self._wrapper._query(
            "helpdesk.ticket",
            "read",
            [[ticket_id]],
            {"fields": ["name", "description", "stage_id", "team_id", "partner_id"]},
        )
        return results[0] if results else {}

    def list_client_tickets(self, partner_id: int, limit: int = 10) -> list[dict]:
        return self._wrapper._query(
            "helpdesk.ticket",
            "search_read",
            [[("partner_id", "=", partner_id)]],
            {
                "fields": ["id", "name", "stage_id", "team_id"],
                "limit": limit,
                "order": "id desc",
            },
        ) or []
