# budget

BUDGET_TICKET_EXTRACTION_PROMPT = """
Extrae la información necesaria para crear un presupuesto desde este ticket.

Devuelve solo JSON válido con esta estructura:
{{
  "company_name": "string",
  "project_summary": "string",
  "requirements": ["string"]
}}

Reglas:
- No inventes datos.
- company_name debe salir del contenido del ticket, del cliente informado o del email.
- Si no puedes identificar una empresa, usa el nombre del cliente informado.
- Los requirements deben ser conceptos buscables en el catálogo de productos/servicios.
- Devuelve requirements concretos, por ejemplo CRM, helpdesk, ventas, formación, soporte o integración.
- No extraigas ni modifiques el partner_id.

Contenido del ticket:
{ticket_text}
"""


BUDGET_PRODUCT_SELECTION_PROMPT = """
Selecciona productos reales del catálogo para crear un presupuesto.

Solicitud:
{request_json}

Catálogo:
{catalog_text}

Devuelve solo JSON válido con esta estructura:
{{
  "product_ids": [1, 2],
  "unmatched_requirements": ["string"]
}}

Reglas:
- Elige solo IDs que aparezcan en el catálogo.
- Elige el producto más cercano por lógica, no solo por coincidencia exacta.
- Si el requisito es "Presupuesto CRM", "CRM comercial" o similar, debe encajar con el producto CRM.
- No inventes productos.
- No devuelvas explicaciones.
"""


BUDGET_REPLY_PROMPT = """
Cliente: {company_name}
Resumen de solicitud: {project_summary}
Servicios incluidos: {product_names}
Perfil cliente: {customer_profile}
Snapshot catálogo: {catalog_snapshot}
Líneas del presupuesto: {order_lines}
Referencia del presupuesto: {sale_order_id}
Importe total: {total} {currency}
Productos relacionados sugeridos: {related_products}
Conceptos no resueltos: {unmatched_requirements}

Escribe una respuesta final lista para enviar en el chat.
"""

ANSWER_BOT_PROMPT = (
    "Eres un asistente comercial que responde en español de forma clara y profesional. "
    "Redacta un mensaje breve y natural para el cliente usando solo la información proporcionada. "
    "No inventes servicios, precios, ids ni datos que no estén en el contexto. "
    "Menciona el presupuesto creado, el total, los servicios incluidos y sugiere un siguiente paso. "
    "Si hay productos relacionados, puedes sugerirlos de forma opcional y prudente."
)

# sales agent

SALES_TICKET_EXTRACTION_PROMPT = """
Extrae la información comercial necesaria para crear una oportunidad CRM desde este ticket.

Devuelve solo JSON válido con esta estructura:
{{
  "company_name": "string",
  "sales_summary": "string",
  "commercial_goals": ["string"],
  "next_step": "string"
}}

Reglas:
- No inventes datos.
- company_name debe salir del ticket, del cliente informado o del email.
- commercial_goals debe contener objetivos comerciales concretos, como pipeline, leads, oportunidades, seguimiento o automatización comercial.
- next_step debe ser una frase breve y útil para orientar la oportunidad en CRM.
- Devuelve solo JSON válido.

Contenido del ticket:
{ticket_text}
"""

SALES_REPLY_PROMPT = """
Cliente: {company_name}
Resumen comercial: {sales_summary}
Objetivos comerciales detectados: {commercial_goals}
Siguiente paso sugerido: {next_step}
Oportunidad CRM: {crm_summary}

Escribe una respuesta final breve para informar de que la oportunidad comercial se ha creado y del siguiente paso recomendado.
"""

# general agent

GENERAL_AGENT_SYSTEM_PROMPT = (
    "Eres un asistente virtual de soporte al cliente. "
    "Tu objetivo es responder de forma breve, clara y profesional en español. "
    "Si el mensaje no requiere acción inmediata, confirma que ha sido recibido "
    "y que el equipo lo revisará. No inventes información ni hagas promesas concretas."
    "Si no está claro que se haya creado un presupuesto, no preguntes si quieren un presupuesto"
)

GENERAL_AGENT_USER_PROMPT = """
Mensaje o ticket recibido:
{input_text}

Redacta una respuesta breve y profesional para el cliente.
"""

# intake agent

INTAKE_EXTRACTION_PROMPT = """
Eres un agente que analiza emails de clientes y los transforma en solicitudes estructuradas.

Devuelve solo JSON válido con esta estructura:
{{
  "company_name": "string",
  "project_summary": "string",
  "requirements": ["string"],
  "urgency": "baja|media|alta",
  "ticket_type": "budget|issue|discard",
  "missing_information": ["string"]
}}

Reglas:
- Devuelve TODO en español.
- No inventes información.
- company_name debe salir del cuerpo, firma, remitente o dominio del email.
- Ejemplos:
  - "Juan Pérez | ACME" → "ACME"
  - "Saludos, María - Ibertech" → "Ibertech"
  - "Somos NetNova" → "NetNova"

Clasificación:
- Usa "budget" si el cliente pide presupuesto, precios, servicios, automatización, implantación, desarrollo, CRM, ERP, consultoría o información comercial.
- Usa "issue" solo si el cliente reporta un problema técnico, error, incidencia o fallo existente.
- Usa "discard" si no hay petición clara.

- project_summary debe ser corto y en español.
- requirements debe contener necesidades concretas y en español.
- Si faltan datos importantes, añádelos en missing_information.
- Devuelve únicamente JSON válido.

Email:
{email_text}
"""

COMPANY_MATCHING_PROMPT = """
Selecciona la empresa existente que más se parezca a la empresa detectada.

Empresa detectada:
{company_name}

Empresas existentes:
{companies_text}

Devuelve solo JSON válido:
{{
  "company_id": number|null
}}

Reglas:
- Selecciona una empresa solo si el parecido es claro.
- Acepta diferencias pequeñas como mayúsculas, tildes, abreviaturas o S.L.
- Si ninguna se parece claramente, usa company_id = null.
- No inventes empresas.
"""
