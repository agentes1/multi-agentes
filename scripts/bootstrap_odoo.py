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
    "api_notifier",
]

PRODUCTS = [
    {
        "name": "CRM Base",
        "list_price": 1200,
        "description": "Implantacion base de CRM para leads, oportunidades, actividades y pipeline.",
        "default_code": "crm",
        "type": "service",
    },
    {
        "name": "Automatizacion Comercial",
        "list_price": 1800,
        "description": "Automatizacion de tareas comerciales, secuencias y reglas de asignacion.",
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
        "description": "Configuracion de presupuestos, pedidos, tarifas y ciclo de venta.",
        "default_code": "sales",
        "type": "service",
    },
    {
        "name": "Implantacion Odoo",
        "list_price": 2500,
        "description": "Analisis, parametrizacion inicial, puesta en marcha y acompanamiento.",
        "default_code": "implantacion_odoo",
        "type": "service",
    },
    {
        "name": "Formacion de Usuarios",
        "list_price": 900,
        "description": "Formacion funcional para usuarios finales, responsables y administradores.",
        "default_code": "formacion",
        "type": "service",
    },
    {
        "name": "Soporte Mensual",
        "list_price": 600,
        "description": "Bolsa mensual de soporte funcional y pequenos ajustes.",
        "default_code": "soporte_mensual",
        "type": "service",
    },
    {
        "name": "Desarrollo a Medida",
        "list_price": 3200,
        "description": "Funcionalidades personalizadas, automatizaciones e integraciones especificas.",
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
    {
        "name": "Asistente Virtual Helpdesk",
        "list_price": 2100,
        "description": "Agente IA para clasificar tickets y responder consultas frecuentes.",
        "default_code": "ai_helpdesk",
        "type": "service",
    },
    {
        "name": "Ingesta de Correos Gmail",
        "list_price": 1300,
        "description": "Entrada automatica de correos y conversion en tickets de Odoo.",
        "default_code": "gmail_ingesta",
        "type": "service",
    },
    {
        "name": "Dashboard Comercial",
        "list_price": 1600,
        "description": "Panel de ventas, oportunidades, conversion y actividad comercial.",
        "default_code": "dashboard_ventas",
        "type": "service",
    },
    {
        "name": "MCP Tools Pack",
        "list_price": 2400,
        "description": "Herramientas MCP para que los agentes consulten y actualicen Odoo.",
        "default_code": "mcp_tools",
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
    {
        "name": "Retail Norte",
        "is_company": True,
        "email": "it@retailnorte.example",
        "comment": "Cadena retail interesada en ventas, stock y soporte postventa.",
    },
    {
        "name": "Clinica San Prado",
        "is_company": True,
        "email": "admin@clinicasanprado.example",
        "comment": "Cliente de servicios con necesidad de CRM y helpdesk.",
    },
    {
        "name": "Logistica Sur",
        "is_company": True,
        "email": "operaciones@logisticasur.example",
        "comment": "Empresa logistica con procesos de incidencias y seguimiento.",
    },
    {
        "name": "EducaPlus",
        "is_company": True,
        "email": "direccion@educaplus.example",
        "comment": "Academia interesada en automatizar solicitudes y ventas.",
    },
    {
        "name": "Laura Cliente",
        "is_company": False,
        "email": "laura.cliente@example.com",
        "comment": "Contacto demo para consultas comerciales.",
    },
    {
        "name": "Martin Pruebas",
        "is_company": False,
        "email": "martin.pruebas@example.com",
        "comment": "Contacto demo para soporte tecnico.",
    },
]

TEAMS = ["Presupuestos", "Soporte cliente", "Ventas"]
TYPES = ["Presupuesto", "Soporte", "Venta"]
CATEGORIES = ["Consulta presupuesto", "Interno", "Problema", "Consulta comercial", "Postventa"]
STAGES = ["New", "In Progress", "Awaiting", "Done", "Cancelled", "Rejected"]
TAGS = ["Urgente", "Cliente nuevo", "Pendiente validacion", "Faltan datos", "Demo", "IA"]

TICKETS = [
    {
        "name": "Solicito presupuesto para implantar CRM",
        "team": "Presupuestos",
        "type": "Presupuesto",
        "category": "Consulta presupuesto",
        "customer": "ACME",
        "tags": ["Cliente nuevo", "Pendiente validacion"],
        "description": "El cliente quiere propuesta para CRM Base, automatizacion comercial y formacion inicial.",
    },
    {
        "name": "Presupuesto para asistente virtual",
        "team": "Presupuestos",
        "type": "Presupuesto",
        "category": "Consulta presupuesto",
        "customer": "EducaPlus",
        "tags": ["IA", "Faltan datos"],
        "description": "Necesitan estimacion para agente IA que atienda correos y cree tickets automaticamente.",
    },
    {
        "name": "Error al crear ticket desde correo",
        "team": "Soporte cliente",
        "type": "Soporte",
        "category": "Problema",
        "customer": "MEGACORP",
        "tags": ["Urgente"],
        "description": "El cliente indica que algunos correos entrantes no generan ticket en Odoo.",
    },
    {
        "name": "Duda sobre seguimiento postventa",
        "team": "Soporte cliente",
        "type": "Soporte",
        "category": "Postventa",
        "customer": "Martin Pruebas",
        "tags": ["Demo"],
        "description": "Consulta sobre como revisar el estado de incidencias abiertas desde el portal.",
    },
    {
        "name": "Interes en contratar soporte mensual",
        "team": "Ventas",
        "type": "Venta",
        "category": "Consulta comercial",
        "customer": "Retail Norte",
        "tags": ["Cliente nuevo"],
        "description": "Cliente pide informacion comercial sobre soporte mensual, SLA y bolsa de horas.",
    },
    {
        "name": "Oportunidad para dashboard comercial",
        "team": "Ventas",
        "type": "Venta",
        "category": "Consulta comercial",
        "customer": "Logistica Sur",
        "tags": ["Pendiente validacion", "Faltan datos"],
        "description": "El cliente quiere analizar un dashboard de ventas conectado con CRM y pedidos.",
    },
]

INBOX_EMAILS = [
    {
        "subject": "Solicitud de presupuesto para CRM y automatizacion",
        "customer": "ACME",
        "email_to": "ventas@local.test",
        "message_id": "<budget-acme-crm-001@demo.local>",
        "body_html": """
            <p>Hola,</p>
            <p>Somos ACME y queremos recibir un presupuesto para implantar CRM Base
            y Automatizacion Comercial en nuestro equipo de ventas.</p>
            <p>Actualmente tenemos 8 usuarios comerciales y necesitamos seguimiento
            de oportunidades, actividades y pipeline.</p>
            <p>Gracias.</p>
        """,
    },
    {
        "subject": "Presupuesto para asistente virtual de soporte",
        "customer": "MEGACORP",
        "email_to": "soporte@local.test",
        "message_id": "<budget-megacorp-ai-helpdesk-001@demo.local>",
        "body_html": """
            <p>Buenos dias,</p>
            <p>Nos interesa un asistente virtual que pueda clasificar correos,
            crear tickets automaticamente y responder consultas frecuentes.</p>
            <p>Tambien queremos valorar soporte mensual tras la puesta en marcha.</p>
            <p>Un saludo.</p>
        """,
    },
    {
        "subject": "Consulta comercial sobre implantacion de Odoo",
        "customer": "Retail Norte",
        "email_to": "ventas@local.test",
        "message_id": "<budget-retailnorte-odoo-001@demo.local>",
        "body_html": """
            <p>Hola equipo,</p>
            <p>Necesitamos una propuesta para Implantacion Odoo, modulo de Ventas
            y configuracion basica de stock.</p>
            <p>Somos una cadena retail con varias tiendas y queremos centralizar
            pedidos, clientes y seguimiento comercial.</p>
            <p>Gracias.</p>
        """,
    },
    {
        "subject": "Necesitamos dashboard comercial conectado con CRM",
        "customer": "Logistica Sur",
        "email_to": "ventas@local.test",
        "message_id": "<budget-logisticasur-dashboard-001@demo.local>",
        "body_html": """
            <p>Buenas,</p>
            <p>Queremos presupuesto para un Dashboard Comercial conectado al CRM
            y al seguimiento de oportunidades.</p>
            <p>Nos interesa medir conversion, volumen de oportunidades y actividad
            por comercial.</p>
            <p>Saludos.</p>
        """,
    },
    {
        "subject": "Presupuesto para ingesta de correos Gmail",
        "customer": "Clinica San Prado",
        "email_to": "soporte@local.test",
        "message_id": "<budget-clinica-gmail-001@demo.local>",
        "body_html": """
            <p>Hola,</p>
            <p>Queremos automatizar la entrada de correos desde Gmail para que se
            creen tickets en Odoo y se derive cada caso al equipo correcto.</p>
            <p>Tambien necesitamos una pequena formacion para administracion.</p>
            <p>Gracias.</p>
        """,
    },
    {
        "subject": "Informacion para automatizar solicitudes de alumnos",
        "customer": "EducaPlus",
        "email_to": "ventas@local.test",
        "message_id": "<budget-educaplus-agent-001@demo.local>",
        "body_html": """
            <p>Buenos dias,</p>
            <p>Somos EducaPlus y queremos presupuesto para automatizar solicitudes
            de alumnos, clasificar mensajes y crear tickets de seguimiento.</p>
            <p>Tambien queremos valorar el producto Asistente Virtual Helpdesk.</p>
            <p>Un saludo.</p>
        """,
    },
]

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


def first(rows):
    """Devuelve el primer registro o None si la busqueda no trae nada."""
    return rows[0] if rows else None


def get_by_name(odoo, table, name):
    """Busca un registro por name exacto."""
    return first(odoo.get_by_value(table, {"name": name}, exact=True))


def get_id_by_name(odoo, table, name):
    """Devuelve el id de un registro por name."""
    row = get_by_name(odoo, table, name)
    return row["id"] if row else False


def create_if_missing(odoo, table, values, label):
    """Crea un registro solo si no existe."""
    found = odoo.get_by_value(table, values, exact=True)

    if found:
        print(f" [~] {label}: {values.get('name') or values.get('key')} already exists")
        return found[0]["id"]

    ids = odoo.create(table, [values])
    print(f" [+] Created {label}: {values.get('name') or values.get('key')} (ID: {ids[0]})")
    return ids[0]


def upsert_system_parameter(odoo, key, value):
    """Crea o actualiza un parametro de sistema."""
    param = first(odoo.get_by_value(Table.SystemParameter, {"key": key}, exact=True))

    if param:
        odoo.update(Table.SystemParameter, [param["id"]], {"value": value})
    else:
        odoo.create(Table.SystemParameter, [{"key": key, "value": value}])

    print(f" [+] Parameter set: {key} = {value}")


def seed_products(odoo):
    """Crea productos demo de servicios."""
    print("\nSeeding products...")

    for product in PRODUCTS:
        existing = odoo.get_by_value(Table.Product, {"default_code": product["default_code"]}, exact=True)

        if existing:
            print(f" [~] Product: {product['name']} already exists")
            continue

        ids = odoo.create(Table.Product, [product])
        print(f" [+] Created product {product['name']} (ID: {ids[0]})")


def seed_customers(odoo):
    """Crea contactos demo."""
    print("\nSeeding customers...")

    for customer in CUSTOMERS:
        existing = odoo.get_by_value(Table.Contact, {"email": customer["email"]}, exact=True)

        if existing:
            print(f" [~] Customer: {customer['name']} already exists")
            continue

        ids = odoo.create(Table.Contact, [customer])
        print(f" [+] Created customer {customer['name']} (ID: {ids[0]})")


def seed_helpdesk_catalog(odoo):
    """Crea equipos, tipos, categorias, etapas y tags."""
    print("\nSetting up helpdesk catalog...")

    for name in TEAMS:
        create_if_missing(odoo, Table.TicketTeam, {"name": name}, "Team")

    for name in TYPES:
        create_if_missing(odoo, Table.TicketType, {"name": name}, "Type")

    for name in CATEGORIES:
        create_if_missing(odoo, Table.TicketCategory, {"name": name}, "Category")

    for name in STAGES:
        create_if_missing(odoo, Table.TicketStage, {"name": name}, "Stage")

    for name in TAGS:
        create_if_missing(odoo, Table.TicketTag, {"name": name}, "Tag")


def seed_tickets(odoo):
    """Crea dos tickets por cada equipo de helpdesk."""
    print("\nSeeding helpdesk tickets...")

    for item in TICKETS:
        if odoo.get_by_value(Table.Ticket, {"name": item["name"]}, exact=True):
            print(f" [~] Ticket: {item['name']} already exists")
            continue

        partner = get_by_name(odoo, Table.Contact, item["customer"])
        tag_ids = [get_id_by_name(odoo, Table.TicketTag, tag) for tag in item["tags"]]
        tag_ids = [tag_id for tag_id in tag_ids if tag_id]

        ticket = {
            "name": item["name"],
            "description": item["description"],
            "team_id": get_id_by_name(odoo, Table.TicketTeam, item["team"]),
            "type_id": get_id_by_name(odoo, Table.TicketType, item["type"]),
            "category_id": get_id_by_name(odoo, Table.TicketCategory, item["category"]),
            "stage_id": get_id_by_name(odoo, Table.TicketStage, "New"),
            "partner_id": partner["id"] if partner else False,
            "partner_name": partner["name"] if partner else item["customer"],
            "partner_email": partner.get("email") if partner else False,
            "tag_ids": [(6, 0, tag_ids)],
        }

        ids = odoo.create(Table.Ticket, [ticket])
        print(f" [+] Created ticket {item['name']} (ID: {ids[0]})")


def seed_inbox_emails(odoo):
    """Crea correos entrantes demo para que el cron los procese."""
    print("\nSeeding inbox emails...")

    for email in INBOX_EMAILS:
        if odoo.get_by_value(Table.MailInboxMessage, {"message_id": email["message_id"]}, exact=True):
            print(f" [~] Inbox email: {email['subject']} already exists")
            continue

        partner = get_by_name(odoo, Table.Contact, email["customer"])
        sender = partner.get("email") if partner else ""

        values = {
            "subject": email["subject"],
            "email_from": f"{email['customer']} <{sender}>",
            "email_to": email["email_to"],
            "email_cc": "",
            "body_html": email["body_html"],
            "message_id": email["message_id"],
            "partner_id": partner["id"] if partner else False,
            "state": "new",
        }

        ids = odoo.create(Table.MailInboxMessage, [values])
        print(f" [+] Created inbox email {email['subject']} (ID: {ids[0]})")


def ensure_assistant_user(odoo):
    """Crea el usuario del asistente si no existe."""
    print("\nEnsuring assistant user exists...")

    user = first(odoo.get_by_value(Table.User, {"login": ASSISTANT_USER["login"]}, exact=True))
    if user:
        print(f" [~] User: {ASSISTANT_USER['login']} already exists")
        return

    contact = {
        "name": ASSISTANT_USER["name"],
        "email": ASSISTANT_USER["email"],
        "company_type": "person",
    }
    partner_id = odoo.create(Table.Contact, [contact])[0]

    values = dict(ASSISTANT_USER)
    values["partner_id"] = partner_id

    ids = odoo.create(Table.User, [values])
    print(f" [+] Created assistant user {ASSISTANT_USER['login']} (ID: {ids[0]})")


def configure_system_parameters(odoo):
    """Configura parametros del backend y Gmail."""
    print("\nConfiguring system parameters...")

    for key, value in SYSTEM_PARAMETERS.items():
        upsert_system_parameter(odoo, key, value)

    print("\nConfiguring Gmail OAuth parameters...")

    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

    if client_id:
        upsert_system_parameter(odoo, "google_gmail_client_id", client_id)
    else:
        print(" [~] GOOGLE_CLIENT_ID not found. Skipping google_gmail_client_id.")

    if client_secret:
        upsert_system_parameter(odoo, "google_gmail_client_secret", client_secret)
    else:
        print(" [~] GOOGLE_CLIENT_SECRET not found. Skipping google_gmail_client_secret.")


if __name__ == "__main__":
    print(f"Connecting to Odoo at {ODOO_BASE_URL}...")
    odoo = OdooAPI(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)

    print("\nInstalling modules...")
    for module in MODULES:
        if odoo.install(module):
            print(f" [+] Installed {module}")
        else:
            print(f" [~] {module} already installed")

    odoo.update_module_list()

    seed_products(odoo)
    seed_customers(odoo)
    seed_helpdesk_catalog(odoo)
    seed_tickets(odoo)
    seed_inbox_emails(odoo)
    ensure_assistant_user(odoo)
    configure_system_parameters(odoo)

    print("\nDone.")