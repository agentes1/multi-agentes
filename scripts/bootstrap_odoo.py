import os
from odoo.api import OdooAPI, Table
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME

MODULES = [
    "base",
    "mail",
    "fetchmail",
    "google_gmail",
    "mail_inbox_input",
    "sale_management",
    "stock",
    "crm",
    "helpdesk_mgmt",
    "helpdesk_type",
    "helpdesk_motive",
    "helpdesk_virtual_assistant",
]

PRODUCTS = [
    {
        "name": "CRM Base",
        "list_price": 1200,
        "description": (
            "Implantacion base de CRM para gestionar leads, oportunidades, actividades "
            "comerciales y seguimiento del pipeline."
        ),
        "default_code": "crm",
        "type": "service",
    },
    {
        "name": "Automatizacion Comercial",
        "list_price": 1800,
        "description": (
            "Automatizacion de tareas comerciales, secuencias de seguimiento, reglas de "
            "asignacion y procesos de captacion de clientes."
        ),
        "default_code": "automatizacion_comercial",
        "type": "service",
    },
    {
        "name": "Helpdesk y Soporte",
        "list_price": 950,
        "description": "Gestion de incidencias, soporte y seguimiento postventa.",
        "default_code": "helpdesk",
        "type": "service",
    },
    {
        "name": "Ventas",
        "list_price": 1100,
        "description": (
            "Configuracion del modulo de ventas para presupuestos, pedidos, tarifas "
            "comerciales y seguimiento del ciclo de venta."
        ),
        "default_code": "sales",
        "type": "service",
    },
    {
        "name": "Implantacion Odoo",
        "list_price": 2500,
        "description": (
            "Servicio de analisis, parametrizacion inicial, puesta en marcha y acompanamiento "
            "para implantar Odoo en la empresa."
        ),
        "default_code": "implantacion_odoo",
        "type": "service",
    },
    {
        "name": "Formacion de Usuarios",
        "list_price": 900,
        "description": (
            "Sesiones de formacion funcional para usuarios finales, responsables de equipo "
            "y administradores del sistema."
        ),
        "default_code": "formacion",
        "type": "service",
    },
    {
        "name": "Soporte Mensual",
        "list_price": 600,
        "description": (
            "Bolsa mensual de soporte funcional y pequenos ajustes para acompanar la "
            "operacion diaria tras la implantacion."
        ),
        "default_code": "soporte_mensual",
        "type": "service",
    },
    {
        "name": "Desarrollo a Medida",
        "list_price": 3200,
        "description": (
            "Desarrollo de funcionalidades personalizadas, automatizaciones avanzadas "
            "e integraciones especificas para Odoo."
        ),
        "default_code": "desarrollo_medida",
        "type": "service",
    },
    {
        "name": "Conector con Odoo",
        "list_price": 1500,
        "description": "Integracion con Odoo para clientes, oportunidades y presupuestos.",
        "default_code": "odoo_connector",
        "type": "service",
    },
]

CUSTOMERS = [
    {
        "name": "ACME",
        "is_company": True,
        "email": "contacto@acme.example",
        "comment": "Cliente pyme orientado a procesos comerciales y CRM.",
    },
    {
        "name": "MEGACORP",
        "is_company": True,
        "email": "contacto@megacorp.example",
        "comment": "Cliente enterprise con interes en implantaciones y soporte continuo.",
    },
    {
        "name": "Alejandro Demo",
        "is_company": False,
        "email": "alejandro@example.com",
        "comment": "Contacto demo para pruebas funcionales de tickets, chat y presupuestos.",
    },
]

TEAMS = ["Presupuestos", "Soporte cliente"]
TYPES = ["Presupuesto", "Soporte"]
CATEGORIES = ["Consulta presupuesto", "Interno", "Problema"]
STAGES = ["New", "In Progress", "Awaiting", "Done", "Cancelled", "Rejected"]
TAGS = ["Urgente", "Cliente nuevo", "Pendiente validacion", "Faltan datos"]

ASSISTANT_USER = {
    "login": "asistente.virtual",
    "name": "Asistente Virtual",
    "email": "asistente.virtual@local.test",
}

SYSTEM_PARAMETERS = {
    "helpdesk_virtual_assistant.backend_ticket_entry_url": "http://assistant-backend:8000/assistant/ticket-entry",
    "helpdesk_virtual_assistant.backend_discuss_message_url": "http://assistant-backend:8000/assistant/discuss-message",
    "helpdesk_virtual_assistant.backend_sales_from_ticket_url": "http://assistant-backend:8000/assistant/sales-from-ticket",
    "mail_inbox_input.backend_incoming_email_url": "http://assistant-backend:8000/assistant/incoming-email",
}


if __name__ == '__main__':
    print(f"Connecting to Odoo at {ODOO_BASE_URL}...")
    odoo = OdooAPI(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)

    print("\nInstalling modules...")
    for module in MODULES:
        if odoo.install(module): print(f' [+] Installed {module}')
        else: print(f' [~] {module} already installed')
    odoo.update_module_list()
    
    print("\nSeeding products...")
    for p in PRODUCTS:
        if odoo.get_by_value(Table.Product, p): 
            print(f' [~] Product: {p['name']} already exists')
        else:
            ids = odoo.create(Table.Product, [p])
            print(f" [+] Created product {p['name']} (ID: {ids[0]})")
    
    print("\nSeeding customers...")
    for c in CUSTOMERS:
        if odoo.get_by_value(Table.Contact, c):
            print(f' [~] Customer: {c['name']} already exists')
        else:
            ids = odoo.create(Table.Contact, [c])
            print(f" [+] Created customer {c['name']} (ID: {ids[0]})")

    print("\nSetting up helpdesk catalog...")
    for t in TEAMS:
        team = {'name': t}
        if odoo.get_by_value(Table.TicketTeam, team):
            print(f" [~] Team {t} already exists.")
        else: 
            odoo.create(Table.TicketTeam, [team])
            print(f' [+] Created Team: {t}')

    for t in TYPES:
        type = {'name': t}
        if odoo.get_by_value(Table.TicketType, type):
            print(f" [~] Type {t} already exists.")
        else: 
            odoo.create(Table.TicketType, [type])
            print(f' [+] Created Type: {t}')

    for c in CATEGORIES:
        category = {'name': c}
        if odoo.get_by_value(Table.TicketCategory, category):
            print(f" [~] Category: {c} already exists.")
        else: 
            odoo.create(Table.TicketCategory, [category])
            print(f' [+] Created Category: {c}')

    for s in STAGES:
        stage = {'name': s}
        if odoo.get_by_value(Table.TicketStage, stage):
            print(f" [~] Stage: {s} already exists.")
        else: 
            odoo.create(Table.TicketStage, [stage])
            print(f' [+] Created Stage: {s}')

    for t in TAGS:
        tag = {'name': t}
        if odoo.get_by_value(Table.TicketTag, tag): 
            print(f" [~] Tag: {t} already exists.")
        else: 
            odoo.create(Table.TicketTag, [tag])
            print(f' [+] Created Tag: {t}')

    print("\nEnsuring assistant user exists...")
    user = odoo.get_by_value(Table.User, ASSISTANT_USER, exact=True)
    if not user:
        contact = { 
            'name': ASSISTANT_USER['name'], 
            'email': ASSISTANT_USER['email'], 
            'company_type': 'person' 
        }
        ids = odoo.create(Table.Contact, [contact])
        user = ASSISTANT_USER
        user['partner_id'] = ids[0]
        odoo.create(Table.User, [user])

    print("\nConfiguring system parameters...")
    for k,v in SYSTEM_PARAMETERS.items():
        param = odoo.get_by_value(Table.SystemParameter, {'key': k}, exact=True)
        if param: odoo.update(Table.SystemParameter, [param[0]['id']], {'value': v})
        else: odoo.create(Table.SystemParameter, [{'key': k, 'value': v}])
        print(f" [+] Parameter set: {k} = {v}")

    print("\nConfiguring Gmail OAuth parameters...")
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

    if not client_id: print(" [~] GOOGLE_CLIENT_ID not found. Skipping google_gmail_client_id.")
    else: 
        p = { 'key': 'google_gmail_client_id', 'value': client_id }
        param = odoo.get_by_value(Table.SystemParameter, {'key': p['key']}, exact=True)
        if param: odoo.update(Table.SystemParameter, [param[0]['id']], {'value': p['value']})
        else: odoo.create(Table.SystemParameter, [p])
        print(" [+] Parameter set: google_gmail_client_id")

    if not client_secret: print(" [~] GOOGLE_CLIENT_SECRET not found. Skipping google_gmail_client_secret.")
    else:
        p = { 'key': 'google_gmail_client_secret', 'value': client_secret }
        param = odoo.get_by_value(Table.SystemParameter, { 'key': p['key'] }, exact=True)
        if param: odoo.update(Table.SystemParameter, [param[0]['id']], {'value': client_secret})
        else: odoo.create(Table.SystemParameter, [p])
        print(" [+] Parameter set: google_gmail_client_secret")
    
