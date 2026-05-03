from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from odoo.api import OdooAPI, Table
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME

mcp = FastMCP("odoo_tools")
odoo = OdooAPI(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)


def product_to_dict(product: dict[str, Any]) -> dict[str, Any]:
    """Normaliza un producto de Odoo para los agentes."""
    return {
        "id": product["id"],
        "name": product.get("name", ""),
        "default_code": product.get("default_code", ""),
        "description": product.get("description") or "",
        "price": product.get("lst_price", 0),
    }


def first(items: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """Devuelve el primer resultado o None."""
    return items[0] if items else None


@mcp.tool()
def list_catalog() -> dict[str, Any]:
    """Devuelve el catálogo presupuestable agrupado por código interno."""
    products = odoo.get_all(Table.Product, ["id", "name", "lst_price", "description", "default_code"]) or {}
    return {p["default_code"]: product_to_dict(p) for p in products if p.get("default_code")}


@mcp.tool()
def find_products_by_text(text: str, limit: int = 5) -> list[dict[str, Any]]:
    """Busca productos por nombre o código."""
    products = odoo.get_by_value(
        Table.Product, {"name": text, "default_code": text},
        ["id", "name", "default_code", "lst_price", "description"], OR=True, limit=limit,
    ) or []
    return [product_to_dict(p) for p in products]


@mcp.tool()
def get_product(product_id: int) -> dict[str, Any] | None:
    """Obtiene un producto por ID."""
    product = first(odoo.get_by_id(Table.Product, [product_id], ["id", "name", "default_code", "lst_price", "description"]))
    return product_to_dict(product) if product else None


@mcp.tool()
def get_product_catalog_snapshot(product_ids: list[int]) -> list[dict[str, Any]]:
    """Obtiene un resumen de varios productos."""
    products = odoo.get_by_id(Table.Product, product_ids, ["id", "name", "default_code", "lst_price", "description"]) or []
    return [product_to_dict(p) for p in products]


@mcp.tool()
def find_related_products(product_ids: list[int], limit: int = 3) -> list[dict[str, Any]]:
    """Sugiere productos relacionados de forma simple."""
    selected = get_product_catalog_snapshot(product_ids)
    if not selected: return []

    terms = set()
    for product in selected:
        name = product.get("name", "").lower()
        if "crm" in name: terms.update(["ventas", "helpdesk"])
        if "helpdesk" in name or "soporte" in name: terms.update(["crm", "ventas"])
        if "automatizacion" in name or "automatización" in name: terms.update(["crm", "helpdesk"])

    suggestions, seen_ids = [], set(product_ids)
    for term in terms:
        for product in find_products_by_text(term, limit=limit):
            if product["id"] in seen_ids: continue
            suggestions.append(product)
            seen_ids.add(product["id"])
            if len(suggestions) >= limit: return suggestions

    return suggestions


@mcp.tool()
def find_company(name: str, exact: bool = False, limit: int = 5) -> list[dict[str, Any]]:
    """Busca empresas en Odoo."""
    operator = "=" if exact else "ilike"
    return odoo.search_read(
        Table.Contact, [("is_company", "=", True), ("name", operator, name)],
        ["id", "name", "email", "is_company"], limit=limit,
    ) or []


@mcp.tool()
def get_or_create_contact(company_name: str, email: str | None = None) -> int:
    """Busca o crea una empresa cliente."""
    contact = first(odoo.get_by_value(Table.Contact, {"name": company_name}, ["id", "name"], exact=True, limit=1))
    if contact: return contact["id"]

    values = {"name": company_name, "is_company": True}
    if email: values["email"] = email

    ids = odoo.create(Table.Contact, [values])
    if not ids: raise RuntimeError("No se pudo crear el contacto en Odoo.")
    return ids[0]


@mcp.tool()
def get_customer_profile(company_name: str) -> dict[str, Any]:
    """Devuelve información básica del cliente."""
    contact = first(odoo.get_by_value(Table.Contact, {"name": company_name}, ["id", "name", "email", "is_company"], limit=1))
    if not contact: return {"known_customer": False, "segment": "desconocido", "email": ""}

    return {
        "known_customer": True,
        "partner_id": contact["id"],
        "name": contact.get("name", ""),
        "email": contact.get("email") or "",
        "is_company": contact.get("is_company", False),
        "segment": "standard",
    }


@mcp.tool()
def get_customer_history(partner_id: int, limit: int = 10) -> dict[str, Any]:
    """Recupera pedidos y tickets anteriores del cliente."""
    orders = odoo.search_read(Table.Order, [("partner_id", "=", partner_id)], ["id", "name", "state", "amount_total", "date_order"], limit=limit) or []
    tickets = odoo.search_read(Table.Ticket, [("partner_id", "=", partner_id)], ["id", "name", "stage_id", "team_id"], limit=limit) or []
    return {"orders": orders, "tickets": tickets}


@mcp.tool()
def find_sale_order_by_client_ref(client_order_ref: str) -> dict[str, Any] | None:
    """Busca un presupuesto por referencia externa."""
    return first(odoo.search_read(
        Table.Order, [("client_order_ref", "=", client_order_ref)],
        ["id", "name", "partner_id", "client_order_ref", "amount_total", "amount_untaxed"], limit=1,
    ))


@mcp.tool()
def create_sale_order(partner_id: int, client_order_ref: str | None = None) -> int:
    """Crea la cabecera de un presupuesto."""
    values = {"partner_id": partner_id}
    if client_order_ref: values["client_order_ref"] = client_order_ref

    ids = odoo.create(Table.Order, [values])
    if not ids: raise RuntimeError("No se pudo crear el presupuesto.")
    return ids[0]


@mcp.tool()
def create_sale_order_line(order_id: int, product_id: int, quantity: int = 1) -> int:
    """Añade una línea al presupuesto."""
    ids = odoo.create(Table.OrderLine, [{"order_id": order_id, "product_id": product_id, "product_uom_qty": quantity}])
    if not ids: raise RuntimeError("No se pudo crear la línea del presupuesto.")
    return ids[0]


@mcp.tool()
def get_sale_order(order_id: int) -> dict[str, Any] | None:
    """Lee la cabecera de un presupuesto."""
    return first(odoo.get_by_id(Table.Order, [order_id], ["id", "name", "partner_id", "client_order_ref", "amount_untaxed", "amount_total"]))


@mcp.tool()
def get_sale_order_lines(order_id: int) -> list[dict[str, Any]]:
    """Lee las líneas de un presupuesto."""
    return odoo.search_read(
        Table.OrderLine, [("order_id", "=", order_id)],
        ["id", "name", "product_id", "product_uom_qty", "price_unit", "price_subtotal"],
    ) or []


@mcp.tool()
def find_helpdesk_team(name: str) -> dict[str, Any] | None:
    """Busca un equipo de Helpdesk."""
    return first(odoo.get_by_value(Table.HelpdeskTeam, {"name": name}, ["id", "name"], exact=True, limit=1))


@mcp.tool()
def find_ticket_type(name: str) -> dict[str, Any] | None:
    """Busca un tipo de ticket."""
    return first(odoo.get_by_value(Table.TicketType, {"name": name}, ["id", "name"], exact=True, limit=1))


@mcp.tool()
def find_ticket_category(name: str) -> dict[str, Any] | None:
    """Busca una categoría de ticket."""
    return first(odoo.get_by_value(Table.TicketCategory, {"name": name}, ["id", "name"], exact=True, limit=1))


@mcp.tool()
def find_ticket_tags(names: list[str]) -> list[int]:
    """Busca etiquetas de ticket y devuelve sus IDs."""
    tag_ids = []
    for name in names:
        tag = first(odoo.get_by_value(Table.TicketTag, {"name": name}, ["id", "name"], exact=True, limit=1))
        if tag: tag_ids.append(tag["id"])
    return tag_ids


@mcp.tool()
def create_helpdesk_ticket(
    title: str, description: str, team_id: int, priority: str = "1",
    type_id: int | None = None, category_id: int | None = None,
    tag_ids: list[int] | None = None, partner_id: int | None = None,
    partner_name: str | None = None, partner_email: str | None = None,
    origin_channel: str = "email",
) -> int:
    """Crea un ticket de Helpdesk en Odoo."""
    values = {"name": title, "description": description, "team_id": team_id, "priority": priority}

    if type_id: values["type_id"] = type_id
    if category_id: values["category_id"] = category_id
    if tag_ids: values["tag_ids"] = [(6, 0, tag_ids)]
    if partner_id: values["partner_id"] = partner_id
    if partner_name: values["partner_name"] = partner_name
    if partner_email: values["partner_email"] = partner_email

    origin = str(origin_channel or "").lower()
    context = {"assistant_ticket_origin": origin} if origin else {}
    if origin == "email":
        context.update({"skip_virtual_assistant_chat": True, "skip_virtual_assistant_followup": True})

    ids = odoo.create(Table.Ticket, [values], context=context)
    if not ids: raise RuntimeError("No se pudo crear el ticket en Odoo.")
    return ids[0]


@mcp.tool()
def post_message_to_ticket(ticket_id: int, body: str) -> bool:
    """Publica una respuesta en el chatter del ticket."""
    result = odoo._query(
        Table.Ticket, "message_post", [[ticket_id]],
        {"body": body, "message_type": "comment", "subtype_xmlid": "mail.mt_comment"},
    )
    return bool(result)


if __name__ == "__main__":
    mcp.run()