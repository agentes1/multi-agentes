{
    "name": "Mail Inbox Input",
    "version": "18.0.1.0.0",
    "summary": "Guarda correos entrantes en un modelo propio de Odoo",
    "description": """
        Módulo para simular una bandeja de entrada en Odoo.
        Los correos recibidos por el servidor entrante se crean como registros
        en el modelo mail.inbox.message.
    """,
    "author": "Agentes 1",
    "category": "Productivity",
    "depends": ["base","mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/mail_inbox_message_views.xml",
        "data/fetchmail_server.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}