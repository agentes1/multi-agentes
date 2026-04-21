from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.state import BudgetState
from odoo.tools import build_odoo_tools


def _get_deps(config: RunnableConfig) -> BudgetDependencies:
    deps = config.get("configurable", {}).get("deps")
    if deps is None:
        raise RuntimeError("BudgetDependencies no inyectadas en config")
    return deps


async def _run_tool_calls(response, tools: list) -> list[ToolMessage]:
    tool_map = {t.name: t for t in tools}
    results = []
    for tc in getattr(response, "tool_calls", []):
        tool = tool_map.get(tc["name"])
        if tool:
            try:
                output = await tool.ainvoke(tc.get("args", {}))
                results.append(ToolMessage(content=str(output), tool_call_id=tc.get("id", "")))
            except Exception as e:
                results.append(ToolMessage(content=f"Error: {e}", tool_call_id=tc.get("id", "")))
    return results


# TOOL-CALLING: el LLM consulta Odoo para enriquecer el contexto del presupuesto.
# Solo lectura — los errores son silenciosos para no bloquear el flujo principal.
# Las mutaciones (buscar productos, crear partner, crear orden) ocurren en nodos siguientes.
async def enrich_context_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)
    normalized = state.get("normalized_request", {})
    company_name = normalized.get("company_name", "")
    requirements = normalized.get("requirements", [])

    prompt = (
        f"Consulta el catálogo de Odoo y el historial del cliente para preparar el presupuesto. "
        f"Empresa: '{company_name}'. Requisitos solicitados: {requirements}."
    )
    messages = list(state.get("messages", [])) + [HumanMessage(content=prompt)]

    try:
        tools = build_odoo_tools(deps.odoo_service)
        llm_with_tools = deps.llm.bind_tools(tools)
        response = await llm_with_tools.ainvoke(messages)
        tool_messages = await _run_tool_calls(response, tools)
        return {
            "messages": messages + [response] + tool_messages,
            "odoo_context": {"raw_results": [m.content for m in tool_messages]},
        }
    except Exception:
        return {"odoo_context": {}}


async def prepare_budget_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)

    normalized_request = state.get("normalized_request")
    if not normalized_request:
        return {
            "error": "La solicitud normalizada no está disponible. No se puede crear presupuesto.",
            "selected_products": [],
        }

    requirements = normalized_request.get("requirements", [])

    if not requirements:
        return {
            "error": "La solicitud no contiene requisitos. No se puede crear presupuesto.",
            "selected_products": [],
        }

    selected_products: list[dict] = []
    unmatched_requirements: list[str] = []

    try:
        for requirement in requirements:
            value = str(requirement).strip()
            if not value:
                continue

            matches = deps.odoo_service.find_products_by_text(value, limit=5)

            if matches:
                product = matches[0]
                if not any(p["id"] == product["id"] for p in selected_products):
                    selected_products.append(product)
            else:
                unmatched_requirements.append(value)

    except Exception as e:
        return {
            "error": f"Error al consultar productos en Odoo: {e}",
            "selected_products": [],
        }

    if not selected_products:
        return {
            "error": f"No se encontraron productos en Odoo para los requisitos: {requirements}",
            "selected_products": [],
        }

    return {
        "messages": [
            AIMessage(
                content=f"Solicitud preparada para presupuesto con {len(selected_products)} productos encontrados en Odoo"
            )
        ],
        "selected_products": selected_products,
        "unmatched_requirements": unmatched_requirements,
        "error": None,
    }


async def ensure_partner_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)

    normalized_request = state.get("normalized_request") or {}
    company_name = normalized_request.get("company_name", "Desconocido")

    try:
        partner_id = deps.odoo_service.get_or_create_contact(company_name)
    except Exception as e:
        return {"error": f"Error al obtener o crear el contacto en Odoo: {e}"}

    return {
        "messages": [
            AIMessage(content=f"Contacto preparado en Odoo para {company_name} con id {partner_id}")
        ],
        "partner_id": partner_id,
        "error": None,
    }


async def create_odoo_quote_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)

    normalized_request = state.get("normalized_request") or {}
    company_name = normalized_request.get("company_name", "Desconocido")
    selected_products = state.get("selected_products", [])
    partner_id = state.get("partner_id")

    if not partner_id:
        return {"error": "partner_id no disponible. No se puede crear el presupuesto."}

    try:
        sale_order_id = deps.odoo_service.create_sale_order(partner_id=partner_id)

        for product in selected_products:
            deps.odoo_service.create_sale_order_line(
                order_id=sale_order_id,
                product_id=product["id"],
                quantity=1,
            )

        order = deps.odoo_service.get_sale_order(sale_order_id)

    except Exception as e:
        return {"error": f"Error al crear el presupuesto en Odoo: {e}"}

    quote_summary = {
        "company_name": company_name,
        "sale_order_id": sale_order_id,
        "selected_products": [
            {
                "id": product["id"],
                "name": product.get("name", ""),
                "default_code": product.get("default_code", ""),
            }
            for product in selected_products
        ],
        "subtotal": float(order.get("amount_untaxed", 0)),
        "total": float(order.get("amount_total", 0)),
        "currency": "EUR",
    }

    return {
        "messages": [
            AIMessage(
                content=f"Presupuesto creado en Odoo para {company_name}. ID={sale_order_id}, total={quote_summary['total']} EUR"
            )
        ],
        "sale_order_id": sale_order_id,
        "quote_summary": quote_summary,
        "error": None,
    }


async def error_node(state: BudgetState) -> dict:
    error_msg = state.get("error") or "Error desconocido en el agente de presupuestos"
    return {
        "messages": [AIMessage(content=f"No se ha podido crear el presupuesto: {error_msg}")]
    }
