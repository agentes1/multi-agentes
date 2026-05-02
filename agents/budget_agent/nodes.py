import json
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.schemas import BudgetCreateSchema
from agents.budget_agent.state import BudgetState
from shared.prompts import (
    ANSWER_BOT_PROMPT,
    BUDGET_PRODUCT_SELECTION_PROMPT,
    BUDGET_REPLY_PROMPT,
    BUDGET_TICKET_EXTRACTION_PROMPT,
)


def _get_deps(config: RunnableConfig) -> BudgetDependencies:
    """Obtiene las dependencias inyectadas en el grafo."""
    deps = config.get("configurable", {}).get("deps")
    if deps is None:
        raise RuntimeError("BudgetDependencies no inyectadas en config")
    return deps


def _extract_partner_id(ticket_text: str) -> int | None:
    """Extrae el partner_id del texto del ticket."""
    match = re.search(
        r"(?:partner_id|contact_id|contacto_id|id_contacto|id contacto|contact id)\s*[:=]\s*(\d+)",
        ticket_text,
        re.IGNORECASE,
    )
    return int(match.group(1)) if match else None


def _build_ticket_text(ticket: dict) -> str:
    """Convierte un ticket recibido como diccionario en un bloque de texto sencillo."""
    return "\n".join(
        [
            f"Ticket ID: {ticket.get('id') or ''}",
            f"Título: {ticket.get('name') or ticket.get('subject') or ''}",
            f"Descripción: {ticket.get('description') or ticket.get('body') or ''}",
            f"Cliente informado: {ticket.get('partner_name') or ''}",
            f"Email cliente: {ticket.get('partner_email') or ticket.get('email_from') or ''}",
            f"partner_id: {ticket.get('partner_id') or ''}",
        ]
    ).strip()


def _catalog_items(catalog: object) -> list[dict]:
    """Normaliza el catálogo para trabajar siempre con una lista de productos."""
    if isinstance(catalog, dict):
        return [
            {
                "id": item.get("id"),
                "name": item.get("name", ""),
                "default_code": item.get("default_code") or code,
                "description": item.get("description", ""),
                "price": item.get("price", 0),
            }
            for code, item in catalog.items()
            if isinstance(item, dict) and item.get("id")
        ]

    if isinstance(catalog, list):
        return [item for item in catalog if isinstance(item, dict) and item.get("id")]

    return []


def _product_catalog_text(products: list[dict]) -> str:
    """Prepara el catálogo en texto para que el LLM pueda elegir productos."""
    return "\n".join(
        (
            f'- id={item["id"]}, code="{item.get("default_code", "")}", '
            f'name="{item.get("name", "")}", description="{item.get("description", "")}"'
        )
        for item in products
    )


async def _extract_request_from_ticket(llm, ticket_text: str) -> dict:
    """Extrae company_name, project_summary y requirements desde el ticket."""
    prompt = BUDGET_TICKET_EXTRACTION_PROMPT.format(ticket_text=ticket_text)
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    content = response.content if isinstance(response.content, str) else str(response.content)
    return json.loads(content)


async def _select_products_with_llm(
    llm,
    normalized_request: dict,
    catalog_items: list[dict],
) -> tuple[list[int], list[str]]:
    """Selecciona productos del catálogo usando la solicitud normalizada."""
    prompt = BUDGET_PRODUCT_SELECTION_PROMPT.format(
        request_json=json.dumps(normalized_request, ensure_ascii=False),
        catalog_text=_product_catalog_text(catalog_items),
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    content = response.content if isinstance(response.content, str) else str(response.content)
    parsed = json.loads(content)

    product_ids = [int(product_id) for product_id in parsed.get("product_ids", [])]
    unmatched = [str(item) for item in parsed.get("unmatched_requirements", [])]

    return product_ids, unmatched


async def prepare_budget_node(state: BudgetState, config: RunnableConfig) -> dict:
    """Prepara los datos del presupuesto a partir del ticket aceptado."""
    deps = _get_deps(config)
    tools = deps.tools

    ticket_text = (
        _build_ticket_text(state.get("ticket", {}))
        or state.get("ticket_text")
        or state.get("ticket_block")
        or state.get("source_text")
        or ""
    ).strip()

    if not ticket_text and not state.get("normalized_request"):
        return {"error": "No se recibió el contenido del ticket.", "selected_products": []}

    try:
        normalized_request = state.get("normalized_request") or await _extract_request_from_ticket(
            deps.llm,
            ticket_text,
        )
    except Exception:
        return {"error": "El LLM no pudo extraer datos válidos del ticket.", "selected_products": []}

    partner_id = state.get("partner_id") or _extract_partner_id(ticket_text)
    company_name = str(normalized_request.get("company_name") or "").strip()

    if not partner_id:
        try:
            partner_id = tools.get_or_create_contact(company_name or "Desconocido")
        except Exception as exc:
            return {
                "error": f"Error al obtener o crear el cliente en Odoo: {exc}",
                "selected_products": [],
            }

    requirements = normalized_request.get("requirements", [])
    if not requirements:
        return {
            "error": "El ticket no contiene requisitos utilizables para crear el presupuesto.",
            "selected_products": [],
        }

    try:
        products = _catalog_items(tools.list_catalog())
        product_ids, unmatched_requirements = await _select_products_with_llm(
            deps.llm,
            normalized_request,
            products,
        )
        selected_products = [
            product for product in products if int(product["id"]) in product_ids
        ]
    except Exception as exc:
        return {
            "error": f"Error al seleccionar productos del catálogo: {exc}",
            "selected_products": [],
        }

    if not selected_products:
        return {
            "error": f"No se seleccionaron productos de Odoo para los requisitos: {requirements}",
            "selected_products": [],
        }

    return {
        "messages": [
            AIMessage(
                content=f"Ticket preparado para presupuesto con {len(selected_products)} productos encontrados en Odoo"
            )
        ],
        "normalized_request": normalized_request,
        "partner_id": int(partner_id),
        "source_ticket_id": state.get("source_ticket_id") or state.get("ticket", {}).get("id"),
        "selected_products": selected_products,
        "unmatched_requirements": unmatched_requirements,
        "error": None,
    }


async def create_odoo_quote_node(state: BudgetState, config: RunnableConfig) -> dict:
    """Crea o reutiliza el presupuesto en Odoo."""
    deps = _get_deps(config)
    tools = deps.tools

    try:
        budget_data = BudgetCreateSchema.model_validate(
            {
                "partner_id": state.get("partner_id"),
                "company_name": state["normalized_request"].get("company_name")
                or f"partner_id {state.get('partner_id')}",
                "selected_products": state.get("selected_products", []),
            }
        )
    except Exception:
        return {"error": "Los datos preparados para crear el presupuesto no son válidos."}

    source_ticket_id = state.get("source_ticket_id")
    client_order_ref = f"helpdesk-ticket-{source_ticket_id}" if source_ticket_id else None

    try:
        order = tools.find_sale_order_by_client_ref(client_order_ref) if client_order_ref else None

        if order:
            sale_order_id = order["id"]
        else:
            sale_order_id = tools.create_sale_order(
                partner_id=budget_data.partner_id,
                client_order_ref=client_order_ref,
            )

            for product in budget_data.selected_products:
                tools.create_sale_order_line(
                    order_id=sale_order_id,
                    product_id=product["id"],
                    quantity=1,
                )

        sale_order = tools.get_sale_order(sale_order_id)
        order_lines = tools.get_sale_order_lines(sale_order_id)

    except Exception as exc:
        return {"error": f"Error al crear el presupuesto en Odoo: {exc}"}

    quote_summary = {
        "company_name": budget_data.company_name,
        "partner_id": budget_data.partner_id,
        "sale_order_id": sale_order_id,
        "client_order_ref": client_order_ref,
        "selected_products": [
            {
                "id": product["id"],
                "name": product.get("name", ""),
                "default_code": product.get("default_code", ""),
            }
            for product in budget_data.selected_products
        ],
        "order_lines": order_lines,
        "subtotal": float(sale_order.get("amount_untaxed", 0)),
        "total": float(sale_order.get("amount_total", 0)),
        "currency": "EUR",
    }

    return {
        "messages": [
            AIMessage(
                content=(
                    f"Presupuesto creado en Odoo para {budget_data.company_name}. "
                    f"ID={sale_order_id}, total={quote_summary['total']} {quote_summary['currency']}"
                )
            )
        ],
        "sale_order_id": sale_order_id,
        "quote_summary": quote_summary,
        "error": None,
    }


async def compose_budget_reply_node(state: BudgetState, config: RunnableConfig) -> dict:
    """Redacta una respuesta final con el presupuesto creado."""
    deps = _get_deps(config)
    tools = deps.tools

    request = state["normalized_request"]
    quote = state["quote_summary"]
    products = quote.get("selected_products", [])

    company_name = quote.get("company_name", "cliente")
    product_ids = [product["id"] for product in products if product.get("id")]
    product_names = [product.get("name", "") for product in products if product.get("name")]

    customer_profile = tools.get_customer_profile(company_name)
    catalog_snapshot = tools.get_product_catalog_snapshot(product_ids) if product_ids else []
    related_products = tools.find_related_products(product_ids, limit=2) if product_ids else []

    prompt = BUDGET_REPLY_PROMPT.format(
        company_name=company_name,
        project_summary=request.get("project_summary") or "Sin resumen adicional",
        product_names=", ".join(product_names) or "No disponible",
        customer_profile=customer_profile,
        catalog_snapshot=catalog_snapshot,
        order_lines=quote.get("order_lines", []),
        sale_order_id=quote.get("sale_order_id"),
        total=quote.get("total", 0),
        currency=quote.get("currency", "EUR"),
        related_products=related_products or "Ninguno",
        unmatched_requirements=", ".join(state.get("unmatched_requirements", [])) or "Ninguno",
    )

    try:
        response = await deps.llm.ainvoke(
            [
                SystemMessage(content=ANSWER_BOT_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
        reply_text = response.content or ""
    except Exception:
        reply_text = (
            f"Hola {company_name},\n\n"
            f"He generado un presupuesto inicial en Odoo.\n"
            f"Referencia del presupuesto: {quote.get('sale_order_id')}\n"
            f"Importe total estimado: {quote.get('total', 0)} {quote.get('currency', 'EUR')}"
        )

    return {"messages": [AIMessage(content=reply_text.strip())]}


async def error_node(state: BudgetState) -> dict:
    """Devuelve un mensaje de error controlado."""
    error_msg = state.get("error", "Error desconocido en el agente de presupuestos")
    return {
        "messages": [
            AIMessage(content=f"No se ha podido crear el presupuesto: {error_msg}")
        ]
    }