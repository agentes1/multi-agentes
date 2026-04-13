import xmlrpc.client
import time

url = "http://localhost:8069"
db = "odoo"
username = "admin"
password = "admin"

print("Authenticating...")
common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})

if not uid:
    print("Authentication failed.")
    exit(1)

print(f"Authenticated with UID: {uid}")
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))

def execute(*args, **kwargs):
    return models.execute_kw(db, uid, password, *args, **kwargs)

print("Installing sale_management module...")
module_ids = execute('ir.module.module', 'search', [[('name', '=', 'sale_management')]])
if module_ids:
    execute('ir.module.module', 'button_immediate_install', [module_ids])
    print("Installed sale_management.")
    # wait a bit for installation to finish
    time.sleep(5)
else:
    print("sale_management not found.")

print("Installing crm module...")
module_ids = execute('ir.module.module', 'search', [[('name', '=', 'crm')]])
if module_ids:
    execute('ir.module.module', 'button_immediate_install', [module_ids])
    print("Installed crm.")
    time.sleep(5)

# create products
products = [
    {"name": "CRM Base", "list_price": 1200, "description": "Gestión básica de leads, oportunidades y pipeline comercial", "default_code": "crm_base", "type": "service"},
    {"name": "Clasificación de emails con IA", "list_price": 1800, "description": "Clasificación automática de correos y sugerencia de respuesta", "default_code": "email_ai", "type": "service"},
    {"name": "Generación de presupuestos con IA", "list_price": 2200, "description": "Creación asistida de presupuestos a partir de formularios o emails", "default_code": "quotation_ai", "type": "service"},
    {"name": "Conector con Odoo", "list_price": 1500, "description": "Integración con Odoo para clientes, oportunidades y presupuestos", "default_code": "odoo_connector", "type": "service"},
    {"name": "Dashboard comercial", "list_price": 900, "description": "Panel de seguimiento de actividad comercial y embudo", "default_code": "dashboard", "type": "service"},
]

print("Creating products...")
for p in products:
    existing = execute('product.product', 'search', [[('default_code', '=', p['default_code'])]])
    if not existing:
        product_id = execute('product.product', 'create', [p])
        print(f"Created product {p['name']} (ID {product_id})")
    else:
        print(f"Product {p['name']} already exists.")

# create customers
customers = [
    {"name": "ACME", "is_company": True},
    {"name": "MEGACORP", "is_company": True},
]

print("Creating customers...")
for c in customers:
    existing = execute('res.partner', 'search', [[('name', '=', c['name'])]])
    if not existing:
        partner_id = execute('res.partner', 'create', [c])
        print(f"Created customer {c['name']} (ID {partner_id})")
    else:
        print(f"Customer {c['name']} already exists.")

print("Setup complete.")
