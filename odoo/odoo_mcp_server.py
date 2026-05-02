from mcp.server.fastmcp import FastMCP
from __future__ import annotations
from typing import Any

from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME
from odoo.api import OdooAPI, Table

mcp = FastMCP("odoo_tools")
odoo = OdooAPI(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)


@mcp.tool()
def list_catalog() -> dict[str, Any]:
    """Devuelve el catálogo completo de servicios presupuestables desde Odoo."""
    products = odoo.get_all(Table.Product, ['id', 'name', 'lst_price', 'description', 'default_code'])
    if not products: return {}

    result: dict = {}
    for product in products:
        if not product.get('default_code'): continue
        product['price'] = product.pop('lst_price', 0)
        result[product['default_code']] = product

    return result


@mcp.tool()
def find_company(name: str, exact: bool = False, limit: int = 5) -> list[dict[str, Any]]:
    """Busca empresas en Odoo por nombre para enriquecer el contexto del agente."""
    return odoo.get_by_value(
        Table.Contact, 
        { 'is_company': True, 'name': name },
        ['id', 'email', 'name', 'is_company'],
        exact,
        limit
    )


@mcp.tool()
def get_product_catalog_snapshot(product_ids: list[int]) -> list[dict[str, Any]]:
    """Devuelve una vista resumida y enriquecida del catálogo para una lista de productos."""
    products = odoo.get_by_id(Table.Product, product_ids, ['id', 'name', 'default_code', 'lst_price', 'description'])
    for p in products: p['price'] = p.pop('lst_price')
    return products


@mcp.tool()
def find_products_by_text(text: str, limit: int = 5) -> list[dict[str, Any]] | None:
    """Busca productos de Odoo por texto libre."""
    query = {'name': text, 'default_code': text}
    fields = ['id', 'name', 'default_code', 'lst_price']
    products = odoo.get_by_value(Table.Product, query, fields, OR=True, limit=limit)
    return products if products else None


@mcp.tool()
def get_product(product_id: int) -> dict[str, Any] | None:
    """Obtiene el detalle de un producto por su id."""
    results = odoo.get_by_id(Table.Product, [product_id])
    return results[0] if results else None
    

@mcp.tool()
def get_or_create_contact(company_name: str) -> int:
    """Obtiene o crea el contacto del cliente y devuelve su id."""
    contact = odoo.get_by_value(Table.Contact, {'name': company_name}, ['id', 'name'], exact=True)
    if contact: return contact[0]['id'] 
    else: return odoo.create(Table.Contact, [{'name': company_name}])[0]


@mcp.tool()
def get_customer_profile(company_name: str) -> dict[str, Any]:
    '''Devuelve informacion comercial resumida del cliente para personalizar la respuesta.'''
    contacts = odoo.get_by_value(Table.Contact, {'name': company_name}, ['id', 'name', 'email', 'is_company'])
    if not contacts: 
        return { 'segment': 'desconocido', 'known_customer': False, 'email': '' }

    contact = contacts[0] 
    segment = 'standard'

    normalized_name = str(contact.get('name', '')).upper()
    if 'ACME' in normalized_name: segment = 'pyme'
    elif 'MEGACORP' in normalized_name: segment = 'enterprise'

    return {
        'segment': segment,
        'known_customer': True,
        'email': contact.get('email', '') or '',
        'partner_id': contact['id'],
    }


@mcp.tool()
def get_customer_history(partner_id: int, limit: int = 10) -> dict[str, Any]:
    """Recupera historial comercial básico del cliente en Odoo."""
    client_orders = odoo.get_by_value(Table.Order, {'partner_id': partner_id}, ['id', 'name', 'state', 'amount_total', 'date_order'], limit=limit)
    client_tickets = odoo.get_by_value(Table.Ticket, {'partner_id': partner_id}, ['id', 'name', 'stage_id', 'team_id'], limit=limit)
    return { 'orders': client_orders, 'tickets': client_tickets }


@mcp.tool()
<<<<<<< HEAD
def find_sale_order_by_client_ref(client_order_ref: str) -> dict[str, Any] | None:
    """Busca un presupuesto por referencia externa para evitar duplicados."""
    wrapper = _get_wrapper()
    return wrapper.find_sale_order_by_client_ref(client_order_ref)


@mcp.tool()
def create_sale_order(partner_id: int, client_order_ref: str | None = None) -> int:
    """Crea una cabecera de presupuesto en Odoo."""
    wrapper = _get_wrapper()
    return wrapper.create_sale_order(
        partner_id=partner_id,
        client_order_ref=client_order_ref,
    )
=======
def create_sale_order(partner_id: int) -> int | None:
    """Crea una cabecera de presupuesto en Odoo."""
    ids = odoo.create(Table.Order, [{'partner_id': partner_id}])
    return ids[0] if ids else None
>>>>>>> origin


@mcp.tool()
def create_sale_order_line(order_id: int, product_id: int, quantity: int = 1) -> int | None:
    """Añade una línea a un presupuesto existente."""
    ids = odoo.create(Table.OrderLine, [{ 'order_id': order_id, 'product_id': product_id, 'product_uom_qty': quantity }])
    return ids[0] if ids else None


@mcp.tool()
def get_sale_order(order_id: int) -> dict[str, Any] | None:
    """Lee la cabecera de un presupuesto existente."""
    results = odoo.get_by_id(Table.Order, [order_id])
    return results[0] if results else None


@mcp.tool()
def get_sale_order_lines(order_id: int) -> list[dict[str, Any]] | None:
    """Lee las líneas de un presupuesto existente."""
    fields = ['name', 'product_id', 'product_uom_qty', 'price_unit', 'price_subtotal']
    orderlines = odoo.get_by_value(Table.OrderLine, {'order_id': order_id}, fields, exact=True)
    return orderlines if orderlines else None


@mcp.tool()
def find_related_products(product_ids: list[int], limit: int = 3) -> list[dict[str, Any]]:
    """Sugiere productos relacionados a partir de un conjunto de productos ya seleccionados."""
    selected_products = odoo.get_by_id(Table.Product, product_ids, ['id', 'name', 'default_code'])
    if not selected_products: return []

    selected_codes = {str(p.get('default_code', '')).lower() for p in selected_products if p.get('default_code')}
    
    preferred_terms = set()
    for product in selected_products:
        name = str(product.get("name", "")).lower()
        if "crm" in name: preferred_terms.update({"ventas", "sales", "helpdesk"})
        if "automatizacion" in name or "comercial" in name: preferred_terms.update({"crm", "helpdesk"})
        if "helpdesk" in name or "soporte" in name: preferred_terms.update({"crm", "ventas"})

    suggestions: list[dict[str, Any]] = []
    seen_ids = set(product_ids)

    for term in preferred_terms:
        related = odoo.get_by_value(
            Table.Product, 
            {'name': term, 'default_code': term}, 
            ['id', 'name', 'default_code', 'lst_price'], 
            limit=limit
        )
        if not related: continue

        for product in related:
            if product['id'] in seen_ids: continue
            
            product['price'] = product.pop('lst_price', 0)
            suggestions.append(product)
            seen_ids.add(product['id'])
            
            if len(suggestions) >= limit:
                return suggestions

    return suggestions


if __name__ == "__main__":
    mcp.run()
