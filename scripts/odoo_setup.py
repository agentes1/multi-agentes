from odoo_integration.odoo_api_wrapper import OdooAPIWrapper
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD

PRODUCTS = [
    {"name": "CRM Base", "list_price": 1200, "description": "Gestión básica de leads, oportunidades y pipeline comercial", "default_code": "crm_base", "type": "service"},
    {"name": "Clasificación de emails con IA", "list_price": 1800, "description": "Clasificación automática de correos y sugerencia de respuesta", "default_code": "email_ai", "type": "service"},
    {"name": "Generación de presupuestos con IA", "list_price": 2200, "description": "Creación asistida de presupuestos a partir de formularios o emails", "default_code": "quotation_ai", "type": "service"},
    {"name": "Conector con Odoo", "list_price": 1500, "description": "Integración con Odoo para clientes, oportunidades y presupuestos", "default_code": "odoo_connector", "type": "service"},
    {"name": "Dashboard comercial", "list_price": 900, "description": "Panel de seguimiento de actividad comercial y embudo", "default_code": "dashboard", "type": "service"},
]

CUSTOMERS = [
    {"name": "ACME", "is_company": True},
    {"name": "MEGACORP", "is_company": True},
]

if __name__ == "__main__":
    odoo = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)
    
    modules = ['base', 'sale_management', 'stock', 'crm']
    [odoo.install_module(m) for m in modules]

    for p in PRODUCTS:
        if not odoo.search('product.product', [('default_code', '=', p['default_code'])]):
            odoo.create_product(p) 

    for c in CUSTOMERS:
        if not odoo.search('res.partner', [('name', '=', c['name'])]):
            odoo.create_contact(c) 
