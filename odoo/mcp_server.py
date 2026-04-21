from typing import Any
from mcp.server.fastmcp import FastMCP
from shared.config import ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD
from odoo.api import OdooAPIWrapper
from odoo.helpers import Table

mcp = FastMCP("odoo_precios_reales")

# Initialize the wrapper
odoo = OdooAPIWrapper(ODOO_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)

@mcp.tool()
def list_catalog() -> dict[str, Any]:
    """Devuelve el catálogo completo de módulos presupuestables desde Odoo."""
    criteria = {'default_code': ['crm_base', 'email_ai', 'quotation_ai', 'odoo_connector', 'dashboard']}
    # Note: get_by_value uses '=', we might need to adjust for 'in' operator or use search directly
    # For now, let's use search_read via a direct query or helper
    domain = [('default_code', 'in', criteria['default_code'])]
    fields = ['name', 'list_price', 'description', 'default_code']
    records = odoo._query(Table.Product, 'search_read', [domain], {'fields': fields})
    
    catalogo = {}
    for r in records:
        code = r['default_code']
        catalogo[code] = {
            "name": r['name'],
            "price": r['list_price'],
            "description": r['description'] or ""
        }
    return catalogo

@mcp.tool()
def get_product(product_code: str) -> dict[str, Any]:
    """Devuelve el detalle de un producto a partir de su código desde Odoo."""
    catalogo = list_catalog()
    if product_code not in catalogo:
        raise ValueError(f"Producto no encontrado en Odoo: {product_code}")
    return catalogo[product_code]

@mcp.tool()
def get_customer_profile(company_name: str) -> dict[str, Any]:
    """Devuelve información comercial básica del cliente desde Odoo."""
    # Use ilike for case-insensitive search
    domain = [('name', '=ilike', company_name)]
    records = odoo._query(Table.Contact, 'search_read', [domain], {'fields': ['name', 'is_company'], 'limit': 1})
    
    profile = {"segment": "desconocido", "discount_pct": 0, "currency": "EUR"}
    
    if records:
        name = records[0]['name'].upper()
        if 'ACME' in name:
            profile['segment'] = 'pyme'
            profile['discount_pct'] = 10
        elif 'MEGACORP' in name:
            profile['segment'] = 'enterprise'
            profile['discount_pct'] = 15
        else:
            profile['segment'] = 'standard'
    
    return profile

@mcp.tool()
def calculate_quote(product_codes: list[str], company_name: str) -> dict[str, Any]:
    """Calcula subtotal, descuento y total final para la lista de módulos y genera la SO en Odoo."""
    customer = get_customer_profile(company_name)
    
    # 1. Ensure customer exists or find them
    records = odoo.get_by_value(Table.Contact, {'name': company_name}, limit=1)
    if not records:
        partner_id = odoo.create(Table.Contact, {'name': company_name, 'is_company': True})
    else:
        partner_id = records[0]['id']

    # 2. Build order lines
    order_lines = []
    lines_output = []
    subtotal = 0

    for code in product_codes:
        p_records = odoo.get_by_value(Table.Product, {'default_code': code}, fields=['id', 'name', 'list_price'], limit=1)
        if not p_records:
            continue
        p = p_records[0]
        
        # apply discount
        discount = customer.get('discount_pct', 0.0)
        
        # Add to Odoo sale order lines (0, 0, vals) is the create command for one-to-many
        order_lines.append((0, 0, {
            'product_id': p['id'],
            'product_uom_qty': 1,
            'price_unit': p['list_price'],
            'discount': discount,
        }))
        
        lines_output.append({
            "code": code,
            "name": p['name'],
            "unit_price": p['list_price']
        })
        subtotal += p['list_price']

    discount_pct = customer["discount_pct"]
    discount_amount = round(subtotal * discount_pct / 100, 2)
    total = round(subtotal - discount_amount, 2)

    # Create the sale order in Odoo
    if order_lines:
        # Note: 'sale.order' isn't in Table enum yet, but _query handles strings too
        so_id = odoo._query('sale.order', 'create', [{
            'partner_id': partner_id,
            'order_line': order_lines
        }])
    
    return {
        "company_name": company_name,
        "currency": customer["currency"],
        "segment": customer["segment"],
        "discount_pct": discount_pct,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "total": total,
        "lines": lines_output,
    }

if __name__ == "__main__":
    mcp.run()
