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

COMPANY_MATCH_PROMPT = """
Tienes que identificar qué empresa de una lista corresponde a un dominio de email.

Dominio del remitente: {domain}
Empresas en el sistema:
{companies}

Responde SOLO con el nombre exacto de la empresa que corresponda al dominio,
o "NINGUNA" si ninguna encaja razonablemente. Sin explicaciones.
""".strip()

PARTNER_NAME_PROMPT = """
Convierte el identificador de email en un nombre de persona legible.

Identificador: {local_part}

Reglas:
- Separa por puntos, guiones o guiones bajos y capitaliza cada parte.
- "ana.lopez" → "Ana Lopez", "j_garcia" → "J Garcia".
- Si es un alias técnico (info, soporte, admin, contact, hello...), devuelve Información, Soporte, Admin, ... respectivamente.
- Solo el nombre. Sin explicaciones.
""".strip()