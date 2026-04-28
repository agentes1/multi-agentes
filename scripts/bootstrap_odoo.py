import time
import os

from odoo.api_wrapper import OdooAPIWrapper
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
    "mail_inbox_input.backend_incoming_email_url": "http://assistant-backend:8000/assistant/incoming-email",
}


def bootstrap_odoo():
    print(f"Connecting to Odoo at {ODOO_BASE_URL}...")
    odoo = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)

    install_modules(odoo)
    seed_products(odoo)
    seed_customers(odoo)
    seed_helpdesk_catalog(odoo)
    ensure_assistant_user(odoo)
    configure_system_parameters(odoo)
    configure_gmail_oauth(odoo)

    print("\nOdoo bootstrap complete.")


def install_modules(odoo):
    print("\nInstalling modules...")
    print(" - updating module list")
    odoo.update_module_list()
    for module in MODULES:
        print(f" - {module}")
        result = odoo.install_module(module)
        if result:
            print(f"   started installation for {module}")
            time.sleep(5)
        else:
            print(f"   already installed or not found")


def seed_products(odoo):
    print("\nSeeding products...")
    for product in PRODUCTS:
        existing_ids = odoo.search("product.product", [("default_code", "=", product["default_code"])])
        if existing_ids:
            product_id = existing_ids[0]
            odoo.update_product(product_id, product)
            print(f" [~] Updated product {product['default_code']} (ID: {product_id})")
            continue
        product_id = odoo.create_product(product)
        print(f" [+] Created product {product['name']} (ID: {product_id})")


def seed_customers(odoo):
    print("\nSeeding contacts...")
    for customer in CUSTOMERS:
        existing_ids = odoo.search("res.partner", [("name", "=", customer["name"])])
        if existing_ids:
            contact_id = existing_ids[0]
            odoo.update_contact(contact_id, customer)
            print(f" [~] Updated contact {customer['name']} (ID: {contact_id})")
            continue
        contact_id = odoo.create_contact(customer)
        print(f" [+] Created contact {customer['name']} (ID: {contact_id})")


def seed_helpdesk_catalog(odoo):
    print("\nSetting up helpdesk catalog...")
    create_named_records(odoo, "helpdesk.ticket.team", TEAMS, "Team")
    create_named_records(odoo, "helpdesk.ticket.type", TYPES, "Type")
    create_named_records(odoo, "helpdesk.ticket.category", CATEGORIES, "Category")
    create_named_records(odoo, "helpdesk.ticket.stage", STAGES, "Stage")
    create_named_records(odoo, "helpdesk.ticket.tag", TAGS, "Tag")


def create_named_records(odoo, model, values, label):
    for value in values:
        if odoo.search(model, [("name", "=", value)]):
            print(f" [~] {label} {value} already exists.")
            continue
        record_id = odoo._models.execute_kw(
            ODOO_DB,
            odoo._uid,
            ODOO_PASSWORD,
            model,
            "create",
            [{"name": value}],
        )
        print(f" [+] Created {label}: {value} (ID: {record_id})")


def ensure_assistant_user(odoo):
    print("\nEnsuring assistant user exists...")
    user = odoo.get_or_create_internal_user(
        login=ASSISTANT_USER["login"],
        name=ASSISTANT_USER["name"],
        email=ASSISTANT_USER["email"],
    )
    print(f" [+] Assistant user ready: {user['name']} (login: {user['login']})")


def configure_system_parameters(odoo):
    print("\nConfiguring system parameters...")
    for key, value in SYSTEM_PARAMETERS.items():
        odoo.set_system_parameter(key, value)
        print(f" [+] Parameter set: {key} = {value}")


def configure_gmail_oauth(odoo):
    print("\nConfiguring Gmail OAuth parameters...")
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

    if client_id:
        odoo.set_system_parameter("google_gmail_client_id", client_id)
        print(" [+] Parameter set: google_gmail_client_id")
    else:
        print(" [~] GOOGLE_CLIENT_ID not found. Skipping google_gmail_client_id.")

    if client_secret:
        odoo.set_system_parameter("google_gmail_client_secret", client_secret)
        print(" [+] Parameter set: google_gmail_client_secret")
    else:
        print(" [~] GOOGLE_CLIENT_SECRET not found. Skipping google_gmail_client_secret.")


if __name__ == "__main__":
    bootstrap_odoo()
