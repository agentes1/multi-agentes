import json, re
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.schemas import BudgetCreateSchema
from agents.budget_agent.state import BudgetState
from shared.agent_notifications import notify_agent_progress
from shared.prompts import BUDGET_PRODUCT_SELECTION_PROMPT, BUDGET_TICKET_EXTRACTION_PROMPT

REQUIREMENT_RULES = {
    "crm": ("crm", "ventas", "pipeline", "lead", "oportunidad", "seguimiento comercial"),
    "automatizacion comercial": ("automatizacion", "automatización", "seguimiento", "automatizar", "workflow"),
    "formacion": ("formacion", "formación", "capacitar", "capacitacion", "capacitación"),
    "soporte mensual": ("soporte", "mantenimiento", "mensual"),
    "helpdesk": ("helpdesk", "ticket", "incidencia", "soporte tecnico", "soporte técnico"),
    "desarrollo": ("desarrollo", "personalizacion", "personalización", "integracion", "integración"),
}

def get_deps(config: RunnableConfig) -> BudgetDependencies:
    """Recupera las dependencias del agente."""
    deps = config.get("configurable", {}).get("deps")
    if not deps: raise RuntimeError("BudgetDependencies no están configuradas")
    return deps

def notify(state: BudgetState, config: RunnableConfig, message: str, type_: str = "info") -> None:
    """Notifica el avance si existe un cliente asociado."""
    cfg, ticket = config.get("configurable", {}), state.get("ticket") or {}
    partner_id = cfg.get("notify_partner_id") or cfg.get("partner_id") or ticket.get("notify_partner_id")
    if not partner_id: return
    try: partner_id = int(partner_id)
    except (TypeError, ValueError): return
    notify_agent_progress(config={"configurable": {"notify_partner_id": partner_id}}, title="Agente Presupuestos", message=message, type_=type_)

def fail(state: BudgetState, config: RunnableConfig, message: str, type_: str = "danger") -> dict:
    """Corta el flujo dejando el error en el estado."""
    notify(state, config, message, type_)
    return {"error": message, "selected_products": []}

def clean_json(content: object) -> dict:
    """Limpia JSON aunque venga dentro de bloques markdown."""
    text = str(content or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.IGNORECASE).strip()
    return json.loads(text)

def normalize(value: object) -> str:
    """Normaliza texto para comparar mejor."""
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()

def ticket_to_text(ticket: dict) -> str:
    """Convierte el ticket en texto para analizarlo."""
    fields = {
        "Ticket ID": ticket.get("id"),
        "Título": ticket.get("name") or ticket.get("subject"),
        "Descripción": ticket.get("description") or ticket.get("body"),
        "Cliente": ticket.get("partner_name"),
        "Email": ticket.get("partner_email") or ticket.get("email_from"),
        "partner_id": ticket.get("partner_id"),
    }
    return "\n".join(f"{k}: {v}" for k, v in fields.items() if v)

def get_ticket_text(state: BudgetState) -> str:
    """Busca el texto del ticket en las entradas posibles."""
    ticket = state.get("ticket") or {}
    return (ticket_to_text(ticket) or state.get("ticket_text") or state.get("ticket_block") or state.get("source_text") or "").strip()

def extract_partner_id(text: str) -> int | None:
    """Extrae partner_id si viene escrito en el texto."""
    match = re.search(r"partner_id\s*[:=]\s*(\d+)", text, re.IGNORECASE)
    return int(match.group(1)) if match else None

def heuristic_extract_request(ticket: dict, ticket_text: str) -> dict:
    """Saca requisitos básicos sin llamar al LLM."""
    text = normalize(ticket_text)
    requirements = [req for req, terms in REQUIREMENT_RULES.items() if any(term in text for term in terms)]
    if not requirements and "odoo" in text: requirements.append("crm")
    return {
        "company_name": str(ticket.get("partner_name") or ticket.get("company_name") or "Cliente").strip(),
        "project_summary": str(ticket.get("name") or ticket.get("subject") or "Solicitud de presupuesto").strip(),
        "requirements": requirements,
    }

def normalize_catalog(catalog: object) -> list[dict]:
    """Deja el catálogo en una lista simple."""
    items = catalog.values() if isinstance(catalog, dict) else catalog
    if not isinstance(items, list) and not hasattr(items, "__iter__"): return []
    return [{
        "id": int(item["id"]),
        "name": item.get("name", ""),
        "default_code": item.get("default_code", ""),
        "description": item.get("description", ""),
        "price": float(item.get("price") or 0),
    } for item in items if isinstance(item, dict) and item.get("id")]

def catalog_to_text(products: list[dict]) -> str:
    """Prepara el catálogo para el prompt."""
    return "\n".join(
        f'id={p["id"]}, code="{p["default_code"]}", name="{p["name"]}", description="{p["description"]}", price="{p["price"]}"'
        for p in products
    )

async def extract_request(llm, ticket_text: str) -> dict:
    """Pide al LLM que entienda el ticket."""
    prompt = BUDGET_TICKET_EXTRACTION_PROMPT.format(ticket_text=ticket_text)
    return clean_json((await llm.ainvoke([HumanMessage(content=prompt)])).content)

async def select_products(llm, request: dict, catalog: list[dict]) -> tuple[list[dict], list[str]]:
    """Pide al LLM que seleccione productos reales."""
    prompt = BUDGET_PRODUCT_SELECTION_PROMPT.format(
        request_json=json.dumps(request, ensure_ascii=False),
        catalog_text=catalog_to_text(catalog),
    )
    result = clean_json((await llm.ainvoke([HumanMessage(content=prompt)])).content)
    ids = {int(pid) for pid in result.get("product_ids", [])}
    return [p for p in catalog if p["id"] in ids], [str(x) for x in result.get("unmatched_requirements", [])]

def product_matches(product: dict, *words: str) -> bool:
    """Comprueba si un producto contiene alguna palabra clave."""
    text = normalize(" ".join(str(product.get(k, "")) for k in ("name", "description", "default_code")))
    return any(word in text for word in words)

def find_product(requirement: str, catalog: list[dict]) -> dict | None:
    """Busca el mejor producto por reglas simples."""
    req = normalize(requirement)
    rules = [(req,), ("crm", "automat", "comercial") if req in {"automatizacion comercial", "crm"} else (), ("form", "capacit") if req == "formacion" else ()]
    return next((p for words in rules for p in catalog if words and product_matches(p, *words)), None)

def heuristic_select_products(request: dict, catalog: list[dict]) -> tuple[list[dict], list[str]]:
    """Selecciona productos sin LLM si hay coincidencia clara."""
    selected, unmatched, seen = [], [], set()
    for req in request.get("requirements") or []:
        product = find_product(req, catalog)
        if product and product["id"] not in seen:
            selected.append(product); seen.add(product["id"])
        elif not product:
            unmatched.append(str(req))
    return selected, unmatched

async def prepare_budget_node(state: BudgetState, config: RunnableConfig) -> dict:
    """Prepara cliente, requisitos y productos."""
    notify(state, config, "Analizando el ticket para preparar un presupuesto...")
    deps, ticket, ticket_text = get_deps(config), state.get("ticket") or {}, get_ticket_text(state)
    if not ticket_text and not state.get("normalized_request"): return fail(state, config, "No se recibió contenido del ticket.", "warning")
    try:
        notify(state, config, "Extrayendo requisitos del ticket...")
        request = state.get("normalized_request") or heuristic_extract_request(ticket, ticket_text)
        if not request.get("requirements"):
            notify(state, config, "Usando el LLM para extraer requisitos del ticket...")
            request = await extract_request(deps.llm, ticket_text)
    except Exception as exc:
        return fail(state, config, f"No se pudieron extraer los datos del ticket: {exc}")
    if not request.get("requirements"): return fail(state, config, "El ticket no contiene requisitos suficientes para crear un presupuesto.", "warning")
    try:
        tools = deps.tools
        company = str(request.get("company_name") or "Cliente desconocido").strip()
        email = ticket.get("partner_email") or ticket.get("email_from") or request.get("customer_email")
        partner_id = state.get("partner_id") or ticket.get("partner_id") or extract_partner_id(ticket_text)
        if not partner_id:
            notify(state, config, "Buscando o creando contacto en Odoo...")
            partner_id = tools.get_or_create_contact(company, email)
        notify(state, config, "Cargando catálogo de productos de Odoo...")
        catalog = normalize_catalog(tools.list_catalog())
        if not catalog: return fail(state, config, "No hay productos disponibles en Odoo.", "warning")
        notify(state, config, "Seleccionando productos adecuados para el presupuesto...")
        selected, unmatched = heuristic_select_products(request, catalog)
        if not selected:
            notify(state, config, "No hubo coincidencia directa. Consultando al LLM...")
            selected, unmatched = await select_products(deps.llm, request, catalog)
    except Exception as exc:
        return fail(state, config, f"Error preparando el presupuesto: {exc}")
    if not selected: return fail(state, config, "No se encontraron productos adecuados para los requisitos del ticket.", "warning")
    notify(state, config, f"Presupuesto preparado con {len(selected)} producto(s).", "success")
    return {
        "messages": [AIMessage(content=f"Presupuesto preparado con {len(selected)} productos.")],
        "normalized_request": request,
        "partner_id": int(partner_id),
        "source_ticket_id": state.get("source_ticket_id") or ticket.get("id"),
        "selected_products": selected,
        "unmatched_requirements": unmatched,
        "error": None,
    }

async def create_odoo_quote_node(state: BudgetState, config: RunnableConfig) -> dict:
    """Crea o reutiliza el presupuesto en Odoo."""
    notify(state, config, "Validando datos para crear el presupuesto en Odoo...")
    tools = get_deps(config).tools
    try:
        budget = BudgetCreateSchema.model_validate({
            "partner_id": state.get("partner_id"),
            "company_name": state["normalized_request"].get("company_name") or f"partner_id {state.get('partner_id')}",
            "selected_products": state.get("selected_products") or [],
        })
    except Exception as exc:
        return {"error": f"Datos inválidos para crear presupuesto: {exc}"}
    ticket_id = state.get("source_ticket_id")
    client_ref = f"helpdesk-ticket-{ticket_id}" if ticket_id else None
    try:
        notify(state, config, "Comprobando si ya existe un presupuesto para este ticket...")
        order = tools.find_sale_order_by_client_ref(client_ref) if client_ref else None
        if order:
            sale_order_id = order["id"]
            notify(state, config, f"Ya existe un presupuesto asociado: ID {sale_order_id}.")
        else:
            notify(state, config, "Creando presupuesto en Odoo...")
            sale_order_id = tools.create_sale_order(budget.partner_id, client_ref)
            for product in budget.selected_products:
                notify(state, config, f"Añadiendo producto: {product.get('name') or product['id']}...")
                tools.create_sale_order_line(sale_order_id, product["id"], 1)
        sale_order = tools.get_sale_order(sale_order_id)
        lines = tools.get_sale_order_lines(sale_order_id)
        if not sale_order: return {"error": "El presupuesto se creó, pero no se pudo recuperar desde Odoo."}
    except Exception as exc:
        return {"error": f"Error creando presupuesto en Odoo: {exc}"}
    quote = {
        "company_name": budget.company_name,
        "partner_id": budget.partner_id,
        "sale_order_id": sale_order_id,
        "sale_order_name": sale_order.get("name"),
        "client_order_ref": client_ref,
        "selected_products": [{"id": p["id"], "name": p.get("name", ""), "default_code": p.get("default_code", "")} for p in budget.selected_products],
        "order_lines": lines,
        "subtotal": float(sale_order.get("amount_untaxed") or 0),
        "total": float(sale_order.get("amount_total") or 0),
        "currency": sale_order.get("currency") or "EUR",
    }
    notify(state, config, f"Presupuesto creado correctamente: {quote.get('sale_order_name') or sale_order_id}. Total: {quote['total']} {quote['currency']}.", "success")
    return {
        "messages": [AIMessage(content=f"Presupuesto creado en Odoo. ID={sale_order_id}, total={quote['total']} {quote['currency']}")],
        "sale_order_id": sale_order_id,
        "quote_summary": quote,
        "error": None,
    }

def build_reply(state: BudgetState, quote: dict, related: list[dict]) -> str:
    """Crea el mensaje final para el ticket."""
    products = quote.get("selected_products") or []
    names = [p["name"] for p in products if p.get("name")]
    text = (
        f"He creado un presupuesto inicial para {quote.get('company_name') or 'cliente'}. "
        f"Referencia: {quote.get('sale_order_name') or quote.get('sale_order_id')}. "
        f"Total estimado: {quote.get('total', 0)} {quote.get('currency', 'EUR')}. "
        f"Servicios incluidos: {', '.join(names) or 'No disponible'}."
    )
    suggestions = ", ".join(p.get("name", "") for p in related if p.get("name"))
    if suggestions: text += f" Como sugerencia adicional, también podríamos valorar: {suggestions}."
    unmatched = ", ".join(state.get("unmatched_requirements") or [])
    if unmatched: text += f" Quedan por concretar estos puntos: {unmatched}."
    return text

async def compose_budget_reply_node(state: BudgetState, config: RunnableConfig) -> dict:
    """Redacta y publica la respuesta del presupuesto."""
    notify(state, config, "Redactando respuesta para el ticket...")
    tools, quote = get_deps(config).tools, state["quote_summary"]
    product_ids = [p["id"] for p in quote.get("selected_products") or [] if p.get("id")]
    try:
        notify(state, config, "Consultando contexto adicional...")
        tools.get_customer_profile(quote.get("company_name") or "cliente")
        tools.get_product_catalog_snapshot(product_ids) if product_ids else []
        related = tools.find_related_products(product_ids, limit=2) if product_ids else []
    except Exception:
        related = []
        notify(state, config, "No se pudo recuperar contexto adicional.", "warning")
    reply, ticket_id = build_reply(state, quote, related), state.get("source_ticket_id")
    if ticket_id:
        try:
            notify(state, config, "Publicando respuesta en el ticket de Odoo...")
            tools.post_message_to_ticket(int(ticket_id), reply)
            notify(state, config, "Respuesta publicada correctamente.", "success")
        except Exception:
            notify(state, config, "No se pudo publicar la respuesta, pero el presupuesto fue generado.", "warning")
    notify(state, config, "Proceso de presupuesto finalizado.", "success")
    return {"messages": [AIMessage(content=reply)], "final_reply": reply}

async def error_node(state: BudgetState, config: RunnableConfig) -> dict:
    """Responde cuando el flujo falla."""
    error = state.get("error") or "Error desconocido en el agente de presupuestos"
    notify(state, config, f"No se ha podido crear el presupuesto: {error}", "danger")
    return {"messages": [AIMessage(content=f"No se ha podido crear el presupuesto: {error}")]}