from odoo.api import OdooAPIWrapper
from odoo.helpers import Table 
from dotenv import load_dotenv
from os import getenv
from halo import Halo

# MODULES = ['base', 'sale_management', 'stock', 'crm', 'helpdesk_mgmt', 'helpdesk_type', 'helpdesk_motive']
MODULES = [ 'base', 'mail', 'fetchmail', 'google_gmail', 'stock', 'crm', 'helpdesk_mgmt', 'helpdesk_type', 'helpdesk_motive', "mail_inbox_input", ]

PRODUCTS = [
    {"name": "CRM Base", "list_price": 1200, "description": "Gestión básica de leads, oportunidades y pipeline comercial", "default_code": "crm_base", "type": "service"},
    {"name": "Clasificación de emails con IA", "list_price": 1800, "description": "Clasificación automática de correos y sugerencia de respuesta", "default_code": "email_ai", "type": "service"},
    {"name": "Generación de presupuestos con IA", "list_price": 2200, "description": "Creación asistida de presupuestos a partir de formularios o emails", "default_code": "quotation_ai", "type": "service"},
    {"name": "Conector con Odoo", "list_price": 1500, "description": "Integración con Odoo para clientes, oportunidades y presupuestos", "default_code": "odoo_connector", "type": "service"},
    {"name": "Dashboard comercial", "list_price": 900, "description": "Panel de seguimiento de actividad comercial y embudo", "default_code": "dashboard", "type": "service"},
]

CONTACTS = [
    {"name": "ACME", "is_company": True},
    {"name": "MEGACORP", "is_company": True},
]

TICKET_TEAMS = ["Presupuestos", "Soporte cliente"]
TICKET_TYPES = ["Presupuesto", "Soporte"]
TICKET_CATEGORIES = ["Consulta presupuesto", "Interno", "Problema"]
TICKET_STAGES = ["New", "In Progress", "Awaiting", "Done", "Cancelled", "Rejected"]
TICKET_TAG = ["Urgente", "Cliente nuevo", "Pendiente validación", "Faltan datos"]


if __name__ == "__main__":
    load_dotenv()
    odoo = OdooAPIWrapper(getenv('ODOO_BASE_URL'), getenv('ODOO_USERNAME'), getenv('ODOO_PASSWORD'), getenv('ODOO_DB'))
    
    spinner = Halo(spinner='dots').start()
    
    spinner.text = 'Updating module list'
    odoo._query('ir.module.module', 'update_list')

    
    for i, m in enumerate(MODULES):
        spinner.text = f"{i+1}/{len(MODULES)} Installing {m}"
        odoo.install(m) 

    spinner.succeed("Modules Installed")
    spinner.start()

    spinner.text = 'Populating Products'

    for p in PRODUCTS:
        if not odoo.get_by_value(Table.Product, p):
            odoo.create(Table.Product, [p])

    spinner.text = 'Populating Contacts'
    for c in CONTACTS:
        if not odoo.get_by_value(Table.Contact, c):
            odoo.create(Table.Contact, [c])
        
    spinner.text = 'Populating Ticket Teams'
    for t in TICKET_TEAMS:
        if not odoo.get_by_value(Table.TicketTeam, {'name': t}):
            odoo.create(Table.TicketTeam, [{'name': t}])

    spinner.text = 'Populating Ticket Types'
    for t in TICKET_TYPES:
        if not odoo.get_by_value(Table.TicketType, {'name': t}):
            odoo.create(Table.TicketType, [{'name': t}])

    spinner.text = 'Populating Ticket Categories'
    for c in TICKET_CATEGORIES:
        if not odoo.get_by_value(Table.TicketCategory, {'name': c}):
            odoo.create(Table.TicketCategory, [{'name': c}])

    spinner.text = 'Populating Ticket Stages'
    for s in TICKET_STAGES:
        if not odoo.get_by_value(Table.TicketStage, {'name': s}):
            odoo.create(Table.TicketStage, [{'name': s}])

    spinner.text = 'Populating Ticket Tags'
    for tag in TICKET_TAG:
        if not odoo.get_by_value(Table.TicketTag, {'name': tag}):
            odoo.create(Table.TicketTag, [{'name': tag}])

    spinner.text = "Configuring Gmail OAuth parameters"

    client_id = getenv("GOOGLE_CLIENT_ID")
    client_secret = getenv("GOOGLE_CLIENT_SECRET")

    if client_id:
        odoo.set_param("google_gmail_client_id", client_id)

    if client_secret:
        odoo.set_param("google_gmail_client_secret", client_secret)

    spinner.succeed("Odoo DB Populated")
