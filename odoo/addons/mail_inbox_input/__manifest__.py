{
    "name": "Mail Inbox Input",
    "version": "18.0.1.0.0",
    "summary": "Guarda correos entrantes y los envía al intake agent",
    "description": """
        Módulo para registrar correos entrantes en Odoo y delegar su
        procesamiento al intake agent del backend.
    """,
    "author": "Agentes 1 + Local Custom",
    "category": "Productivity",
    "depends": ["base", "mail", "google_gmail"],
    "data": [
        "security/ir.model.access.csv",
        "views/mail_inbox_message_views.xml",
        "data/fetchmail_server.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
