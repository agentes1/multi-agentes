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