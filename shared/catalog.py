NORMALIZATION_SYSTEM_PROMPT = """
Eres un asistente que normaliza correos de soporte para crear tickets en Odoo Helpdesk.

Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura:
{
  "title": "string",
  "description": "string",
  "customer_name": "string | null",
  "customer_email": "string | null",
  "company_name": "string | null",
  "partner_name": "string | null",
  "team": "string | null",
  "ticket_type": "string | null",
  "category": "string | null",
  "stage": "string | null",
  "priority": "string | null",
  "tags": []
}

Reglas:
- "title" debe salir del asunto si existe; si no, resume el problema en una frase corta.
- "description" debe contener el contenido útil del correo, limpio y claro.
- "customer_name" debe ser null si no se puede inferir con seguridad.
- "customer_email" debe ser el email del remitente si viene informado.
- "company_name" debe ser el nombre de la empresa si aparece en el correo.
- "partner_name" debe ser el nombre de la persona de contacto.
- No inventes datos. No añadas markdown.
""".strip()

# mapeo de prioridad normalizada a código Odoo (0=Normal, 1=Alta)
PRIORITY_TO_ODOO: dict[str, str] = {
    "baja": "0",
    "media": "0",
    "alta": "1",
}

# mapea el tipo canónico al nombre de tipo de ticket en Odoo
CANONICAL_TYPE_TO_ODOO_NAME: dict[str, str] = {
    "budget": "Presupuesto",
    "issue": "Incidencia",
    "discard": "Consulta General",
}

# equipo, tipo, categoría y tags por defecto para cada tipo canónico de ticket
DEFAULT_TICKET_BLUEPRINTS: dict[str, dict] = {
    "budget": {
        "team_name": "Soporte",
        "ticket_type": "Presupuesto",
        "category": None,
        "default_tags": [],
    },
    "issue": {
        "team_name": "Soporte",
        "ticket_type": "Incidencia",
        "category": None,
        "default_tags": ["Bug"],
    },
    "discard": {
        "team_name": "Soporte",
        "ticket_type": "Consulta General",
        "category": None,
        "default_tags": [],
    },
}


def normalize_priority(value: str | None) -> str:
    raw = (value or "").lower().strip()
    if raw in ("alta", "urgente", "critica", "crítica", "high", "urgent", "critical"):
        return "alta"
    if raw in ("baja", "low", "minor", "trivial", "leve"):
        return "baja"
    return "media"


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