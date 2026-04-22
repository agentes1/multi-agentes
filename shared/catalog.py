NORMALIZATION_SYSTEM_PROMPT = """
Eres un asistente que normaliza correos para crear tickets en Odoo Helpdesk.

Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura:
{
  "title": "string",
  "description": "string",
  "company_name": "string | null",
  "partner_name": "string | null",
  "customer_email": "string | null",
  "team": "string | null",
  "ticket_type": "string | null",
  "category": "string | null",
  "stage": "string | null",
  "tags": ["string"],
  "priority": "string | null"
}

Reglas:
- "title" debe salir del asunto si existe; si no, resume el problema en una frase corta.
- "description" debe contener el contenido útil del correo, limpio y claro.
- "company_name" debe ser la empresa cliente si se puede inferir; si no, null.
- "partner_name" debe ser la persona que envía el correo si se puede inferir; si no, null.
- "customer_email" debe ser el email del remitente si viene informado.
- "team" debe ser null si no se conoce.
- "ticket_type" debe devolver un texto humano, por ejemplo: presupuesto, incidencia, spam.
- "category" debe ser null si no está clara.
- "stage" debe ser null si no está clara.
- "tags" debe ser una lista de strings simples y puede ser vacía.
- "priority" debe devolver un texto humano, por ejemplo: muy urgente, urgente, normal, baja.
- No inventes IDs de Odoo.
- No añadas markdown.
""".strip()

# sinónimos de urgencia para convertir variantes del lenguaje natural
# a los tres valores internos admitidos por el sistema
URGENCY_SYNONYMS = {
    "muy urgente": "alta",
    "urgente": "alta",
    "alta": "alta",

    "normal": "media",
    "media": "media",
    "moderada": "media",
    "medio": "media",

    "baja": "baja",
    "bajo": "baja",
    "poca": "baja",
    "leve": "baja",
}


# normaliza urgencia a uno de los tres valores admitidos
# si no reconoce el valor devuelve "media" por defecto
def normalize_urgency(value: str) -> str:
    normalized = str(value).lower().strip()
    return URGENCY_SYNONYMS.get(normalized, "media")


def normalize_priority(value: str) -> str:
    return normalize_urgency(value)


# sinónimos para clasificar el tipo de solicitud
TICKET_TYPE_SYNONYMS = {
    # presupuesto
    "presupuesto": "budget",
    "cotizacion": "budget",
    "cotización": "budget",
    "precio": "budget",
    "propuesta": "budget",
    "budget": "budget",

    # incidencia
    "incidencia": "issue",
    "problema": "issue",
    "error": "issue",
    "soporte": "issue",
    "bug": "issue",
    "issue": "issue",

    # descarte
    "descartar": "discard",
    "spam": "discard",
    "irrelevante": "discard",
    "discard": "discard",
}


# normaliza tipo de ticket a: budget | issue | discard
# si no reconoce el valor devuelve "discard" por seguridad
def normalize_ticket_type(value: str) -> str:
    normalized = str(value).lower().strip()
    return TICKET_TYPE_SYNONYMS.get(normalized, "discard")

CANONICAL_TYPE_TO_ODOO_NAME = {
    "budget": "Presupuesto",
    "issue": "Soporte",
    "discard": "Soporte",
}

PRIORITY_TO_ODOO = {
    "baja": "0",
    "media": "1",
    "alta": "2",
}

DEFAULT_TICKET_BLUEPRINTS = {
    "budget": {
        "team_name": "Presupuestos",
        "ticket_type": "Presupuesto",
        "category": "Consulta presupuesto",
        "default_tags": [],
    },
    "issue": {
        "team_name": "Soporte cliente",
        "ticket_type": "Soporte",
        "category": "Problema",
        "default_tags": [],
    },
    "discard": {
        "team_name": "Soporte cliente",
        "ticket_type": "Soporte",
        "category": "Interno",
        "default_tags": [],
    },
}
