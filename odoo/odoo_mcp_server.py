from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from odoo.api_wrapper import OdooAPIWrapper
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME

mcp = FastMCP("odoo_tools")


def _get_wrapper() -> OdooAPIWrapper:
    return OdooAPIWrapper(
        url=ODOO_BASE_URL,
        username=ODOO_USERNAME,
        password=ODOO_PASSWORD,
        db=ODOO_DB,
    )


@mcp.tool()
def list_catalog() -> dict[str, Any]:
    """Devuelve el catálogo completo de servicios presupuestables desde Odoo."""
    wrapper = _get_wrapper()
    products = wrapper.list_catalog(limit=200)
    catalog: dict[str, Any] = {}
    for product in products:
        default_code = product.get("default_code")
        if not default_code:
            continue
        catalog[str(default_code)] = {
            "id": product["id"],
            "name": product.get("name", ""),
            "price": float(product.get("lst_price", 0) or 0),
            "description": product.get("description", "") or "",
            "default_code": default_code,
        }
    return catalog


@mcp.tool()
def find_company(name: str, exact: bool = False, limit: int = 5) -> list[dict[str, Any]]:
    """Busca empresas en Odoo por nombre para enriquecer el contexto del agente."""
    wrapper = _get_wrapper()
    return wrapper.find_company(name=name, exact=exact, limit=limit)


@mcp.tool()
def get_product_catalog_snapshot(product_ids: list[int]) -> list[dict[str, Any]]:
    """Devuelve una vista resumida y enriquecida del catálogo para una lista de productos."""
    wrapper = _get_wrapper()
    snapshot: list[dict[str, Any]] = []
    for product_id in product_ids:
        product = wrapper.get_product(product_id)
        if not product:
            continue
        snapshot.append(
            {
                "id": product["id"],
                "name": product.get("name", ""),
                "default_code": product.get("default_code", ""),
                "price": float(product.get("lst_price", 0) or 0),
                "description": product.get("description", "") or "",
            }
        )
    return snapshot


@mcp.tool()
def find_products_by_text(text: str, limit: int = 5) -> list[dict[str, Any]]:
    """Busca productos de Odoo por texto libre."""
    wrapper = _get_wrapper()
    return wrapper.find_products_by_text(text, limit=limit)


@mcp.tool()
def get_product(product_id: int) -> dict[str, Any] | None:
    """Obtiene el detalle de un producto por su id."""
    wrapper = _get_wrapper()
    return wrapper.get_product(product_id)


@mcp.tool()
def get_or_create_contact(company_name: str) -> int:
    """Obtiene o crea el contacto del cliente y devuelve su id."""
    wrapper = _get_wrapper()
    return wrapper.get_or_create_contact(company_name)


@mcp.tool()
def get_customer_profile(company_name: str) -> dict[str, Any]:
    """Devuelve informacion comercial resumida del cliente para personalizar la respuesta."""
    wrapper = _get_wrapper()
    partners = wrapper.search_read(
        "res.partner",
        [("name", "=ilike", company_name)],
        fields=["id", "name", "email", "is_company"],
        limit=1,
    )
    if not partners:
        return {
            "segment": "desconocido",
            "known_customer": False,
            "email": "",
        }

    partner = partners[0]
    segment = "standard"
    normalized_name = str(partner.get("name", "")).upper()
    if "ACME" in normalized_name:
        segment = "pyme"
    elif "MEGACORP" in normalized_name:
        segment = "enterprise"

    return {
        "segment": segment,
        "known_customer": True,
        "email": partner.get("email", "") or "",
        "partner_id": partner["id"],
    }


@mcp.tool()
def get_customer_history(partner_id: int, limit: int = 10) -> dict[str, Any]:
    """Recupera historial comercial básico del cliente en Odoo."""
    wrapper = _get_wrapper()
    return wrapper.get_client_history(partner_id=partner_id, limit=limit)


@mcp.tool()
def create_sale_order(partner_id: int) -> int:
    """Crea una cabecera de presupuesto en Odoo."""
    wrapper = _get_wrapper()
    return wrapper.create_sale_order(partner_id=partner_id)


@mcp.tool()
def create_sale_order_line(order_id: int, product_id: int, quantity: int = 1) -> int:
    """Añade una línea a un presupuesto existente."""
    wrapper = _get_wrapper()
    return wrapper.create_sale_order_line(
        order_id=order_id,
        product_id=product_id,
        quantity=quantity,
    )


@mcp.tool()
def get_sale_order(order_id: int) -> dict[str, Any] | None:
    """Lee la cabecera de un presupuesto existente."""
    wrapper = _get_wrapper()
    return wrapper.get_sale_order(order_id)


@mcp.tool()
def get_sale_order_lines(order_id: int) -> list[dict[str, Any]]:
    """Lee las líneas de un presupuesto existente."""
    wrapper = _get_wrapper()
    return wrapper.get_sale_order_lines(order_id)


@mcp.tool()
def find_related_products(product_ids: list[int], limit: int = 3) -> list[dict[str, Any]]:
    """Sugiere productos relacionados a partir de un conjunto de productos ya seleccionados."""
    wrapper = _get_wrapper()
    selected_products = []
    selected_codes = set()
    for product_id in product_ids:
        product = wrapper.get_product(product_id)
        if not product:
            continue
        selected_products.append(product)
        default_code = product.get("default_code")
        if default_code:
            selected_codes.add(str(default_code).lower())

    suggestions: list[dict[str, Any]] = []
    preferred_terms = set()
    for product in selected_products:
        name = str(product.get("name", "")).lower()
        if "crm" in name:
            preferred_terms.update({"ventas", "sales", "helpdesk"})
        if "automatizacion" in name or "comercial" in name:
            preferred_terms.update({"crm", "helpdesk"})
        if "helpdesk" in name or "soporte" in name:
            preferred_terms.update({"crm", "ventas"})

    for term in preferred_terms:
        for product in wrapper.find_products_by_text(term, limit=limit):
            default_code = str(product.get("default_code", "")).lower()
            if not default_code or default_code in selected_codes:
                continue
            if any(existing["id"] == product["id"] for existing in suggestions):
                continue
            suggestions.append(
                {
                    "id": product["id"],
                    "name": product.get("name", ""),
                    "default_code": product.get("default_code", ""),
                    "price": float(product.get("lst_price", 0) or 0),
                }
            )
            if len(suggestions) >= limit:
                return suggestions

    return suggestions


if __name__ == "__main__":
    mcp.run()
