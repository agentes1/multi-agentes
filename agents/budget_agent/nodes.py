from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.schemas import Budget, BudgetLine
from agents.budget_agent.state import BudgetState

from shared.prompts import NORMALIZE_BUDGET_PROMPT, PRODUCT_MATCH_PROMPT


def _clean(value: Any) -> str | None:
    """Limpia valores vacíos para evitar guardar strings con espacios."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _deps(config: RunnableConfig) -> BudgetDependencies:
    """Obtiene las dependencias del agente desde la configuración del grafo."""
    return config["configurable"]["deps"]


def _ticket_text(state: BudgetState) -> str:
    """Construye el texto del ticket que se usará para crear el presupuesto."""
    ticket = state.get("ticket") or {}
    title = state.get("ticket_title") or ticket.get("title") or ticket.get("name") or ""
    description = state.get("ticket_description") or ticket.get("description") or ""
    company = state.get("company_name") or ticket.get("company_name") or ""
    return f"Empresa: {company}\nTítulo: {title}\nDescripción:\n{description}".strip()


def _format_catalog(catalog: list[dict]) -> str:
    """Convierte el catálogo de Odoo en texto sencillo para el LLM."""
    return "\n".join(
        f"- id={p.get('id')} | name={p.get('name')} | code={p.get('default_code')} | price={p.get('list_price')}"
        for p in catalog
    )


def _format_lines(lines: list[BudgetLine]) -> str:
    """Convierte las líneas del presupuesto en texto sencillo para el LLM."""
    return "\n".join(
        f"- product_name={line.product_name} | quantity={line.quantity}"
        for line in lines
    )


async def normalize_budget_node(state: BudgetState, config: RunnableConfig) -> dict[str, Any]:
    """Convierte el contenido del ticket en un objeto Budget estructurado."""
    text = _ticket_text(state)

    if not text:
        return {"error": "No hay contenido de ticket para crear el presupuesto."}

    try:
        budget = await _deps(config).structured_llm.ainvoke([
            SystemMessage(content=NORMALIZE_BUDGET_PROMPT),
            HumanMessage(content=text),
        ])
        budget = budget if isinstance(budget, Budget) else Budget.model_validate(budget)
    except Exception as e:
        return {"error": f"No se pudo estructurar el presupuesto: {e}"}

    title = _clean(budget.title)
    company_name = _clean(budget.company_name) or _clean(state.get("company_name"))

    lines = [
        line.model_copy(update={
            "product_name": _clean(line.product_name),
            "quantity": max(line.quantity or 1, 1),
        })
        for line in budget.lines
        if _clean(line.product_name)
    ]

    if not title:
        return {"error": "El LLM no devolvió un título válido."}
    if not lines:
        return {"error": "El ticket no contiene productos para presupuestar."}

    return {
        "budget": budget.model_copy(update={
            "title": title,
            "company_name": company_name,
            "notes": _clean(budget.notes),
            "lines": lines,
        }),
    }


async def resolve_products_node(state: BudgetState, config: RunnableConfig) -> dict[str, Any]:
    """Pide al LLM que relacione los productos pedidos con productos reales de Odoo."""
    if state.get("error") or not state.get("budget"):
        return {}

    deps = _deps(config)
    service = deps.odoo_service
    budget: Budget = state["budget"]

    try:
        catalog = service.list_catalog(limit=500)
    except Exception as e:
        return {"error": f"Error al obtener el catálogo de Odoo: {e}"}

    if not catalog:
        return {"error": "El catálogo de Odoo está vacío."}

    try:
        resolved_budget = await deps.structured_llm.ainvoke([
            SystemMessage(content=PRODUCT_MATCH_PROMPT),
            HumanMessage(content=(
                f"Presupuesto actual:\n"
                f"Título: {budget.title}\n"
                f"Empresa: {budget.company_name}\n"
                f"Productos pedidos:\n{_format_lines(budget.lines)}\n\n"
                f"Catálogo de Odoo:\n{_format_catalog(catalog)}"
            )),
        ])
        resolved_budget = resolved_budget if isinstance(resolved_budget, Budget) else Budget.model_validate(resolved_budget)
    except Exception as e:
        return {"error": f"No se pudieron resolver productos con LLM: {e}"}

    catalog_by_id = {p["id"]: p for p in catalog if p.get("id")}
    valid_lines: list[BudgetLine] = []
    unmatched_products: list[str] = []

    for line in resolved_budget.lines:
        product = catalog_by_id.get(line.product_id)

        if not product:
            unmatched_products.append(line.product_name)
            continue

        valid_lines.append(line.model_copy(update={
            "product_id": product["id"],
            "odoo_product_name": product.get("name"),
            "product_code": product.get("default_code"),
            "quantity": max(line.quantity or 1, 1),
        }))

    if not valid_lines:
        return {"error": "No se resolvió ningún producto válido de Odoo."}

    return {
        "budget": budget.model_copy(update={
            "lines": valid_lines,
            "unmatched_products": unmatched_products,
        }),
    }


async def ensure_partner_node(state: BudgetState, config: RunnableConfig) -> dict[str, Any]:
    """Busca la empresa en Odoo o la crea si no existe."""
    if state.get("error") or not state.get("budget"):
        return {}

    service = _deps(config).odoo_service
    budget: Budget = state["budget"]
    company_name = _clean(budget.company_name) or "Cliente nuevo"

    try:
        partner_id = service.get_or_create_contact(company_name)
    except Exception as e:
        return {"error": f"Error al obtener o crear el contacto en Odoo: {e}"}

    return {
        "budget": budget.model_copy(update={
            "company_name": company_name,
            "partner_id": partner_id,
        }),
    }


async def create_quote_node(state: BudgetState, config: RunnableConfig) -> dict[str, Any]:
    """Construye el presupuesto final y lo crea en Odoo."""
    if state.get("error") or not state.get("budget"):
        return {}

    service = _deps(config).odoo_service
    budget: Budget = state["budget"]

    if not budget.partner_id:
        return {"error": "No hay cliente asociado al presupuesto."}

    try:
        sale_order_id = service.create_sale_order(partner_id=budget.partner_id)

        for line in budget.lines:
            if line.product_id:
                service.create_sale_order_line(
                    order_id=sale_order_id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                )

        order = service.get_sale_order(sale_order_id)
    except Exception as e:
        return {"error": f"Error al crear el presupuesto en Odoo: {e}"}

    final_budget = budget.model_copy(update={
        "sale_order_id": sale_order_id,
        "subtotal": float(order.get("amount_untaxed", 0)),
        "total": float(order.get("amount_total", 0)),
        "currency": "EUR",
    })

    return {
        "messages": [
            AIMessage(
                content=(
                    f"Presupuesto creado en Odoo para {final_budget.company_name}. "
                    f"ID={sale_order_id}, total={final_budget.total} EUR."
                )
            )
        ],
        "budget": final_budget,
        "sale_order_id": sale_order_id,
        "quote_summary": final_budget.model_dump(),
    }


async def error_node(state: BudgetState) -> dict[str, Any]:
    """Devuelve un mensaje claro si el agente no puede crear el presupuesto."""
    error_msg = state.get("error") or "Error desconocido en el agente de presupuestos"

    return {
        "messages": [
            AIMessage(content=f"No se ha podido crear el presupuesto: {error_msg}")
        ]
    }