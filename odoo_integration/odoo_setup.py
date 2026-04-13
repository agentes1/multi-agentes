import time
from odoo_integration.odoo_api_wrapper import OdooAPIWrapper
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD

def run_setup():
    print("Connecting to Odoo...")
    odoo = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)
    
    # 1. Install Modules
    modules = ['base', 'sale_management', 'stock'] # contacts, sales, inventory
    for module in modules:
        print(f"Installing {module} module...")
        res = odoo.install_module(module)
        if res:
            print(f"Triggered installation for {module}.")
            time.sleep(5)
        else:
            print(f"Module {module} not found or already installed.")

    # 2. Create Products
    products = [
        {"name": "CRM Base", "list_price": 1200, "description": "Gestión básica de leads, oportunidades y pipeline comercial", "default_code": "crm_base", "type": "service"},
        {"name": "Clasificación de emails con IA", "list_price": 1800, "description": "Clasificación automática de correos y sugerencia de respuesta", "default_code": "email_ai", "type": "service"},
        {"name": "Generación de presupuestos con IA", "list_price": 2200, "description": "Creación asistida de presupuestos a partir de formularios o emails", "default_code": "quotation_ai", "type": "service"},
        {"name": "Conector con Odoo", "list_price": 1500, "description": "Integración con Odoo para clientes, oportunidades y presupuestos", "default_code": "odoo_connector", "type": "service"},
        {"name": "Dashboard comercial", "list_price": 900, "description": "Panel de seguimiento de actividad comercial y embudo", "default_code": "dashboard", "type": "service"},
    ]

    print("Creating products...")
    for p in products:
        existing = odoo._models.execute_kw(ODOO_DB, odoo._uid, ODOO_PASSWORD, 'product.product', 'search', [[('default_code', '=', p['default_code'])]])
        if not existing:
            product_id = odoo.create_product(p)
            print(f"Created product {p['name']} (ID {product_id})")
        else:
            print(f"Product {p['name']} already exists.")

    # 3. Create Customers
    customers = [
        {"name": "ACME", "is_company": True},
        {"name": "MEGACORP", "is_company": True},
    ]

    print("Creating customers...")
    for c in customers:
        existing = odoo._models.execute_kw(ODOO_DB, odoo._uid, ODOO_PASSWORD, 'res.partner', 'search', [[('name', '=', c['name'])]])
        if not existing:
            contact_id = odoo.create_contact(c)
            print(f"Created customer {c['name']} (ID {contact_id})")
        else:
            print(f"Customer {c['name']} already exists.")

    print("Setup complete.")

if __name__ == "__main__":
    run_setup()
