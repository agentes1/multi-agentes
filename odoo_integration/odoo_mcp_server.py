import xmlrpc.client
from typing import Any
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("odoo_precios_reales")

URL = "http://localhost:8069"
DB = "odoo"
USERNAME = "admin"
PASSWORD = "admin"

def _get_odoo_connection():
    common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
    uid = common.authenticate(DB, USERNAME, PASSWORD, {})
    if not uid:
        raise Exception("Odoo authentication failed")
    models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
    return uid, models

def execute(*args, **kwargs):
    uid, models = _get_odoo_connection()
    return models.execute_kw(DB, uid, PASSWORD, *args, **kwargs)

@mcp.tool()
def list_catalog() -> dict[str, Any]:
    """Devuelve el catálogo completo de módulos presupuestables desde Odoo."""
    domain = [('default_code', 'in', ['crm_base', 'email_ai', 'quotation_ai', 'odoo_connector', 'dashboard'])]
    fields = ['name', 'list_price', 'description', 'default_code']
    records = execute('product.product', 'search_read', [domain], {'fields': fields})
    
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
    domain = [('name', '=ilike', company_name)]
    records = execute('res.partner', 'search_read', [domain], {'fields': ['name', 'is_company'], 'limit': 1})
    
    # Defaults just like the mock
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
    domain = [('name', '=ilike', company_name)]
    partner_ids = execute('res.partner', 'search', [domain], {'limit': 1})
    if not partner_ids:
        partner_id = execute('res.partner', 'create', [{'name': company_name, 'is_company': True}])
    else:
        partner_id = partner_ids[0]

    # 2. Build order lines
    order_lines = []
    lines_output = []
    subtotal = 0

    for code in product_codes:
        p_records = execute('product.product', 'search_read', [[('default_code', '=', code)]], {'fields': ['id', 'name', 'list_price'], 'limit': 1})
        if not p_records:
            continue
        p = p_records[0]
        
        # apply discount
        discount = customer.get('discount_pct', 0.0)
        
        # Add to Odoo sale order lines
        # command 0 is to create a new record
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
        so_id = execute('sale.order', 'create', [{
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
