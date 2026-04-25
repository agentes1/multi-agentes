from __future__ import annotations

from typing import Any
from xmlrpc.client import Fault

from odoo.api import OdooAPIWrapper
from odoo.helpers import Table


class OdooService:
    """Capa de dominio sobre OdooAPIWrapper.

    Métodos organizados en tres bloques:
      - Consultas generales   → solo lectura, usadas por tools y nodos
      - Resolución de campos  → antes en resolvers.py, traducen nombres a IDs
      - Mutaciones            → escritura en Odoo, solo desde nodos del grafo
    """

    def __init__(self, wrapper: OdooAPIWrapper) -> None:
        self._wrapper = wrapper

    # CONSULTAS
    # Solo lectura. Si fallan, no modifican nada en Odoo.
    def find_company(self, name: str, exact: bool = False, limit: int = 5) -> list[dict]:
        try:
            operator = "=ilike" if exact else "ilike"
            return self._wrapper._query(
                Table.Contact,
                "search_read",
                [[("is_company", "=", True), ("name", operator, name)]],
                {"fields": ["id", "name", "email", "is_company"], "limit": limit},
            ) or []
        except (Fault, OSError):
            return []

    def find_client(self, name: str) -> dict | None:
        try:
            results = self._wrapper._query(
                Table.Contact,
                "search_read",
                [[("name", "ilike", name), ("active", "=", True)]],
                {"fields": ["id", "name", "email", "phone", "is_company"], "limit": 1},
            )
            return results[0] if results else None
        except (Fault, OSError):
            return None

    def search_products(self, text: str, limit: int = 10) -> list[dict]:
        try:
            return self._wrapper._query(
                Table.Product,
                "search_read",
                [[("name", "ilike", text), ("active", "=", True)]],
                {"fields": ["id", "name", "default_code", "list_price", "type"], "limit": limit},
            ) or []
        except (Fault, OSError):
            return []

    def get_product_by_code(self, code: str) -> dict | None:
        try:
            results = self._wrapper._query(
                Table.Product,
                "search_read",
                [[("default_code", "=", code), ("active", "=", True)]],
                {"fields": ["id", "name", "default_code", "list_price", "type"], "limit": 1},
            )
            return results[0] if results else None
        except (Fault, OSError):
            return None

    def list_catalog(self, limit: int = 100) -> list[dict]:
        try:
            return self._wrapper._query(
                Table.Product,
                "search_read",
                [[("active", "=", True)]],
                {"fields": ["id", "name", "default_code", "list_price"], "limit": limit},
            ) or []
        except (Fault, OSError):
            return []

    def get_client_history(self, partner_id: int) -> dict:
        return {
            "orders": self.list_client_orders(partner_id),
            "tickets": self.list_client_tickets(partner_id),
        }

    def list_client_orders(self, partner_id: int, limit: int = 10) -> list[dict]:
        try:
            return self._wrapper._query(
                Table.SaleOrder,
                "search_read",
                [[("partner_id", "=", partner_id)]],
                {"fields": ["id", "name", "state", "amount_total", "date_order"], "limit": limit, "order": "date_order desc"},
            ) or []
        except (Fault, OSError):
            return []

    def list_client_tickets(self, partner_id: int, limit: int = 10) -> list[dict]:
        try:
            return self._wrapper._query(
                Table.Ticket,
                "search_read",
                [[("partner_id", "=", partner_id)]],
                {"fields": ["id", "name", "stage_id", "team_id"], "limit": limit, "order": "id desc"},
            ) or []
        except (Fault, OSError):
            return []

    def get_order(self, order_id: int) -> dict:
        try:
            results = self._wrapper._query(
                Table.SaleOrder, "read", [[order_id]],
                {"fields": ["name", "state", "amount_untaxed", "amount_total", "date_order"]},
            )
            return results[0] if results else {}
        except (Fault, OSError):
            return {}

    def get_ticket(self, ticket_id: int) -> dict:
        try:
            results = self._wrapper._query(
                Table.Ticket, "read", [[ticket_id]],
                {"fields": ["name", "description", "stage_id", "team_id", "partner_id"]},
            )
            return results[0] if results else {}
        except (Fault, OSError):
            return {}

    def get_sale_order(self, sale_order_id: int) -> dict:
        try:
            results = self._wrapper._query(
                Table.SaleOrder, "read", [[sale_order_id]],
                {"fields": ["name", "partner_id", "amount_untaxed", "amount_total", "state"]},
            )
            return results[0] if results else {}
        except (Fault, OSError):
            return {}

    def find_products_by_text(self, text: str, limit: int = 5) -> list[dict]:
        try:
            return self._wrapper._query(
                Table.Product,
                "search_read",
                [[("name", "ilike", text), ("active", "=", True)]],
                {"fields": ["id", "name", "default_code", "list_price"], "limit": limit},
            ) or []
        except (Fault, OSError):
            return []

    # RESOLUCIÓN DE CAMPOS  
    # Traducen nombres legibles a IDs de Odoo. Solo lectura.

    def find_record_id(self, model: str, name: str | None) -> int | None:
        """Resuelve un nombre al ID de Odoo del modelo indicado."""
        if not name:
            return None
        return self.find_record_id_by_name(model, name)

    def find_record_ids(self, model: str, names: list[str]) -> list[int]:
        """Resuelve varios nombres a IDs ignorando duplicados y vacíos."""
        seen: set[str] = set()
        ids: list[int] = []
        for name in names:
            cleaned = str(name).strip()
            if not cleaned or cleaned.casefold() in seen:
                continue
            seen.add(cleaned.casefold())
            record_id = self.find_record_id(model, cleaned)
            if record_id:
                ids.append(record_id)
        return ids

    def find_record_id_by_name(self, model: str, name: str) -> int | None:
        try:
            results = self._wrapper._query(
                model,
                "search_read",
                [[("name", "=ilike", name)]],
                {"fields": ["id", "name"], "limit": 1},
            )
            return results[0]["id"] if results else None
        except (Fault, OSError):
            return None

    def get_model_fields(self, model: str) -> set[str]:
        """Devuelve los campos disponibles de un modelo de Odoo."""
        try:
            fields_meta = self._wrapper._query(
                model, "fields_get", [], {"attributes": ["string", "type"]},
            )
            return set(fields_meta.keys())
        except (Fault, OSError):
            return set()

    def search_read(self, model: str, domain: list, fields: list[str], limit: int = 100) -> list[dict]:
        """Consulta genérica de solo lectura usada por nodos que necesitan listas de registros."""
        try:
            return self._wrapper._query(
                model, "search_read", [domain], {"fields": fields, "limit": limit},
            ) or []
        except (Fault, OSError):
            return []

    # MUTACIONES
    # Escritura en Odoo. Solo llamadas desde nodos del grafo, nunca desde tools.
    # Razón: crear o modificar registros debe ser determinista, no delegarse al LLM.
    def create_company_contact(self, name: str, email: str | None = None) -> int:
        vals: dict[str, Any] = {"name": name, "is_company": True, "customer_rank": 1}
        if email:
            vals["email"] = email
        return self._wrapper._query(Table.Contact, "create", [vals])

    def get_or_create_contact(self, company_name: str) -> int:
        existing = self._wrapper.get_by_value(
            Table.Contact, {"name": company_name}, fields=["id"], limit=1,
        )
        if existing:
            return existing[0]["id"]
        return self._wrapper._query(
            Table.Contact, "create",
            [{"name": company_name, "is_company": True, "customer_rank": 1}],
        )

    def create_sale_order(self, partner_id: int) -> int:
        return self._wrapper._query(Table.SaleOrder, "create", [{"partner_id": partner_id}])

    def create_sale_order_line(self, order_id: int, product_id: int, quantity: int) -> int:
        return self._wrapper._query(
            Table.SaleOrderLine, "create",
            [{"order_id": order_id, "product_id": product_id, "product_uom_qty": quantity}],
        )

    def create_helpdesk_ticket(
        self,
        name: str,
        description: str,
        partner_id: int | None = None,
        partner_email: str | None = None,
        team_id: int | None = None,
    ) -> int:
        vals = {
            "name": name,
            "description": description,
            **({"partner_id": partner_id} if partner_id else {}),
            **({"partner_email": partner_email} if partner_email else {}),
            **({"team_id": team_id} if team_id else {}),
        }
        return self._wrapper._query(Table.Ticket, "create", [vals])
    
    def create_ticket_from_vals(self, vals: dict[str, Any]) -> int:
        return self._wrapper._query(Table.Ticket, "create", [vals])
