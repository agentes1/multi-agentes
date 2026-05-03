import json, re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.schemas import BudgetCreateSchema
from agents.budget_agent.state import BudgetState
from shared.prompts import ANSWER_BOT_PROMPT, BUDGET_PRODUCT_SELECTION_PROMPT, BUDGET_REPLY_PROMPT, BUDGET_TICKET_EXTRACTION_PROMPT


def get_deps(config: RunnableConfig) -> BudgetDependencies:
    deps = config.get("configurable", {}).get("deps")
    if not deps: raise RuntimeError("BudgetDependencies no están configuradas")
    return deps


def clean_json(content: object) -> dict:
    text = str(content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def ticket_to_text(ticket: dict) -> str:
    fields = {
        "Ticket ID": ticket.get("id"),
        "Título": ticket.get("name") or ticket.get("subject"),
        "Descripción": ticket.get("description") or ticket.get("body"),
        "Cliente": ticket.get("partner_name"),
        "Email": ticket.get("partner_email") or ticket.get("email_from"),
        "partner_id": ticket.get("partner_id"),
    }
    return "\n".join(f"{key}: {value}" for key, value in fields.items() if value)


def get_ticket_text(state: BudgetState) -> str:
    ticket = state.get("ticket") or {}
    return (ticket_to_text(ticket) or state.get("ticket_text") or state.get("ticket_block") or state.get("source_text") or "").strip()


def extract_partner_id(text: str) -> int | None:
    match = re.search(r"partner_id\s*[:=]\s*(\d+)", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def normalize_catalog(catalog: object) -> list[dict]:
    if isinstance(catalog, dict): catalog = catalog.values()
    if not isinstance(catalog, list) and not hasattr(catalog, "__iter__"): return []

    products = []
    for item in catalog:
        if not isinstance(item, dict) or not item.get("id"): continue
        products.append({
            "id": int(item["id"]),
            "name": item.get("name", ""),
            "default_code": item.get("default_code", ""),
            "description": item.get("description", ""),
            "price": float(item.get("price") or 0),
        })
    return products


def catalog_to_text(products: list[dict]) -> str:
    return "\n".join(
        f'id={p["id"]}, code="{p.get("default_code", "")}", name="{p.get("name", "")}", description="{p.get("description", "")}", price="{p.get("price", 0)}"'
        for p in products
    )


async def extract_request(llm, ticket_text: str) -> dict:
    response = await llm.ainvoke([HumanMessage(content=BUDGET_TICKET_EXTRACTION_PROMPT.format(ticket_text=ticket_text))])
    return clean_json(response.content)


async def select_products(llm, request: dict, catalog: list[dict]) -> tuple[list[dict], list[str]]:
    prompt = BUDGET_PRODUCT_SELECTION_PROMPT.format(request_json=json.dumps(request, ensure_ascii=False), catalog_text=catalog_to_text(catalog))
    result = clean_json((await llm.ainvoke([HumanMessage(content=prompt)])).content)

    selected_ids = {int(product_id) for product_id in result.get("product_ids", [])}
    selected_products = [product for product in catalog if product["id"] in selected_ids]
    unmatched = [str(item) for item in result.get("unmatched_requirements", [])]

    return selected_products, unmatched


async def prepare_budget_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = get_deps(config)
    tools = deps.tools
    ticket = state.get("ticket") or {}
    ticket_text = get_ticket_text(state)

    if not ticket_text and not state.get("normalized_request"):
        return {"error": "No se recibió contenido del ticket.", "selected_products": []}

    try:
        request = state.get("normalized_request") or await extract_request(deps.llm, ticket_text)
    except Exception as exc:
        return {"error": f"No se pudieron extraer los datos del ticket: {exc}", "selected_products": []}

    requirements = request.get("requirements") or []
    if not requirements:
        return {"error": "El ticket no contiene requisitos suficientes para crear un presupuesto.", "selected_products": []}

    company_name = str(request.get("company_name") or "").strip()
    customer_email = ticket.get("partner_email") or ticket.get("email_from") or request.get("customer_email")

    try:
        partner_id = state.get("partner_id") or ticket.get("partner_id") or extract_partner_id(ticket_text)

        if not partner_id:
            partner_id = tools.get_or_create_contact(company_name=company_name or "Cliente desconocido", email=customer_email)

        catalog = normalize_catalog(tools.list_catalog())
        if not catalog:
            return {"error": "No hay productos disponibles en Odoo.", "selected_products": []}

        selected_products, unmatched = await select_products(deps.llm, request, catalog)
    except Exception as exc:
        return {"error": f"Error preparando el presupuesto: {exc}", "selected_products": []}

    if not selected_products:
        return {"error": "No se encontraron productos adecuados para los requisitos del ticket.", "selected_products": []}

    return {
        "messages": [AIMessage(content=f"Presupuesto preparado con {len(selected_products)} productos.")],
        "normalized_request": request,
        "partner_id": int(partner_id),
        "source_ticket_id": state.get("source_ticket_id") or ticket.get("id"),
        "selected_products": selected_products,
        "unmatched_requirements": unmatched,
        "error": None,
    }


async def create_odoo_quote_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = get_deps(config)
    tools = deps.tools

    try:
        budget = BudgetCreateSchema.model_validate({
            "partner_id": state.get("partner_id"),
            "company_name": state["normalized_request"].get("company_name") or f"partner_id {state.get('partner_id')}",
            "selected_products": state.get("selected_products") or [],
        })
    except Exception as exc:
        return {"error": f"Datos inválidos para crear presupuesto: {exc}"}

    source_ticket_id = state.get("source_ticket_id")
    client_order_ref = f"helpdesk-ticket-{source_ticket_id}" if source_ticket_id else None

    try:
        existing_order = tools.find_sale_order_by_client_ref(client_order_ref) if client_order_ref else None

        if existing_order:
            sale_order_id = existing_order["id"]
        else:
            sale_order_id = tools.create_sale_order(partner_id=budget.partner_id, client_order_ref=client_order_ref)
            for product in budget.selected_products:
                tools.create_sale_order_line(order_id=sale_order_id, product_id=product["id"], quantity=1)

        sale_order = tools.get_sale_order(sale_order_id)
        order_lines = tools.get_sale_order_lines(sale_order_id)

        if not sale_order:
            return {"error": "El presupuesto se creó, pero no se pudo recuperar desde Odoo."}
    except Exception as exc:
        return {"error": f"Error creando presupuesto en Odoo: {exc}"}

    quote_summary = {
        "company_name": budget.company_name,
        "partner_id": budget.partner_id,
        "sale_order_id": sale_order_id,
        "client_order_ref": client_order_ref,
        "selected_products": [{"id": p["id"], "name": p.get("name", ""), "default_code": p.get("default_code", "")} for p in budget.selected_products],
        "order_lines": order_lines,
        "subtotal": float(sale_order.get("amount_untaxed") or 0),
        "total": float(sale_order.get("amount_total") or 0),
        "currency": sale_order.get("currency") or "EUR",
    }

    return {
        "messages": [AIMessage(content=f"Presupuesto creado en Odoo. ID={sale_order_id}, total={quote_summary['total']} {quote_summary['currency']}")],
        "sale_order_id": sale_order_id,
        "quote_summary": quote_summary,
        "error": None,
    }


async def compose_budget_reply_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = get_deps(config)
    tools = deps.tools
    request, quote = state["normalized_request"], state["quote_summary"]

    company_name = quote.get("company_name") or "cliente"
    products = quote.get("selected_products") or []
    product_ids = [p["id"] for p in products if p.get("id")]
    product_names = [p["name"] for p in products if p.get("name")]

    try:
        customer_profile = tools.get_customer_profile(company_name)
        catalog_snapshot = tools.get_product_catalog_snapshot(product_ids) if product_ids else []
        related_products = tools.find_related_products(product_ids, limit=2) if product_ids else []
    except Exception:
        customer_profile, catalog_snapshot, related_products = {}, [], []

    prompt = BUDGET_REPLY_PROMPT.format(
        company_name=company_name,
        project_summary=request.get("project_summary") or "Sin resumen adicional",
        product_names=", ".join(product_names) or "No disponible",
        customer_profile=customer_profile,
        catalog_snapshot=catalog_snapshot,
        order_lines=quote.get("order_lines") or [],
        sale_order_id=quote.get("sale_order_id"),
        total=quote.get("total") or 0,
        currency=quote.get("currency") or "EUR",
        related_products=related_products or "Ninguno",
        unmatched_requirements=", ".join(state.get("unmatched_requirements") or []) or "Ninguno",
    )

    try:
        response = await deps.llm.ainvoke([SystemMessage(content=ANSWER_BOT_PROMPT), HumanMessage(content=prompt)])
        reply_text = str(response.content or "").strip()
    except Exception:
        reply_text = (
            f"Hola {company_name},\n\n"
            f"He preparado un presupuesto inicial en Odoo.\n"
            f"Referencia: {quote.get('sale_order_id')}\n"
            f"Total estimado: {quote.get('total', 0)} {quote.get('currency', 'EUR')}"
        )

    ticket_id = state.get("source_ticket_id")
    if ticket_id and reply_text:
        try:
            tools.post_message_to_ticket(ticket_id=int(ticket_id), body=reply_text)
        except Exception:
            pass

    return {"messages": [AIMessage(content=reply_text)], "final_reply": reply_text}


async def error_node(state: BudgetState) -> dict:
    error = state.get("error") or "Error desconocido en el agente de presupuestos"
    return {"messages": [AIMessage(content=f"No se ha podido crear el presupuesto: {error}")]}