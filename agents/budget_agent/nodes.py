from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.state import BudgetState

from shared.prompts import ANSWER_BOT_PROMPT


# helper para obtener dependencias inyectadas desde el config del grafo
def _get_deps(config: RunnableConfig) -> BudgetDependencies:
    deps = config.get("configurable", {}).get("deps")
    if deps is None:
        raise RuntimeError("BudgetDependencies no inyectadas en config")
    return deps


# prepara el presupuesto obteniendo los requisitos/productos tal como vienen del json normalizado
# error si no hay requisitos utilizables
async def prepare_budget_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)
    tools = deps.tools

    normalized_request = state["normalized_request"]
    requirements = normalized_request.get("requirements", [])

    # validación mínima: debe haber requisitos para poder construir presupuesto
    if not requirements:
        return {
            "error": "La solicitud no contiene requisitos. No se puede crear presupuesto.",
            "selected_products": [],
        }

    selected_products = []
    unmatched_requirements = []

    try:
        # por cada requisito buscamos coincidencias en los productos reales de Odoo
        for requirement in requirements:
            value = str(requirement).strip()
            if not value:
                continue

            matches = tools.find_products_by_text(value, limit=5)

            # si hay coincidencias, usamos la primera
            if matches:
                product = matches[0]

                # evitamos duplicados por id
                if not any(p["id"] == product["id"] for p in selected_products):
                    selected_products.append(product)
            else:
                unmatched_requirements.append(value)

    except Exception as e:
        return {
            "error": f"Error al consultar productos en Odoo: {e}",
            "selected_products": [],
        }

    # validación: debe haberse encontrado al menos un producto real en Odoo
    if not selected_products:
        return {
            "error": (
                f"No se encontraron productos en Odoo para los requisitos: {requirements}"
            ),
            "selected_products": [],
        }

    return {
        "messages": [
            AIMessage(
                content=(
                    f"Solicitud preparada para presupuesto con "
                    f"{len(selected_products)} productos encontrados en Odoo"
                )
            )
        ],
        "selected_products": selected_products,
        "unmatched_requirements": unmatched_requirements,
        "error": None,
    }


# crea o recupera el contacto del cliente en odoo
# se usa el company_name del json normalizado
async def ensure_partner_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)
    tools = deps.tools

    normalized_request = state["normalized_request"]
    company_name = normalized_request.get("company_name", "Desconocido")

    try:
        partner_id = tools.get_or_create_contact(company_name)
    except Exception as e:
        return {
            "error": f"Error al obtener o crear el contacto en Odoo: {e}",
        }

    return {
        "messages": [
            AIMessage(content=f"Contacto preparado en Odoo para {company_name} con id {partner_id}")
        ],
        "partner_id": partner_id,
        "error": None,
    }


# crea el presupuesto real en odoo usando los productos seleccionados
# por simplicidad, añade una línea por producto con cantidad 1
async def create_odoo_quote_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)
    tools = deps.tools

    normalized_request = state["normalized_request"]
    company_name = normalized_request.get("company_name", "Desconocido")
    selected_products = state.get("selected_products", [])
    partner_id = state["partner_id"]

    try:
        # crea la cabecera del presupuesto
        sale_order_id = tools.create_sale_order(partner_id=partner_id)

        # añade líneas al presupuesto usando directamente los productos ya resueltos desde Odoo
        for product in selected_products:
            tools.create_sale_order_line(
                order_id=sale_order_id,
                product_id=product["id"],
                quantity=1,
            )

        # lee el presupuesto ya creado para devolver un resumen útil
        order = tools.get_sale_order(sale_order_id)
        order_lines = tools.get_sale_order_lines(sale_order_id)

    except Exception as e:
        return {
            "error": f"Error al crear el presupuesto en Odoo: {e}",
        }

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
        "order_lines": order_lines,
        "subtotal": float(order.get("amount_untaxed", 0)),
        "total": float(order.get("amount_total", 0)),
        "currency": "EUR",
    }

    return {
        "messages": [
            AIMessage(
                content=(
                    f"Presupuesto creado en Odoo para {company_name}. "
                    f"ID={sale_order_id}, total={quote_summary['total']} {quote_summary['currency']}"
                )
            )
        ],
        "sale_order_id": sale_order_id,
        "quote_summary": quote_summary,
        "error": None,
    }


async def compose_budget_reply_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)
    tools = deps.tools
    normalized_request = state["normalized_request"]
    quote_summary = state["quote_summary"]
    unmatched_requirements = state.get("unmatched_requirements", [])

    company_name = normalized_request.get("company_name") or quote_summary.get(
        "company_name", "cliente"
    )
    project_summary = normalized_request.get("project_summary", "").strip()
    selected_products = quote_summary.get("selected_products", [])
    product_names = [product.get("name", "").strip() for product in selected_products if product]
    product_ids = [product.get("id") for product in selected_products if product.get("id")]
    total = quote_summary.get("total", 0)
    currency = quote_summary.get("currency", "EUR")
    sale_order_id = quote_summary.get("sale_order_id")
    order_lines = quote_summary.get("order_lines", [])
    customer_profile = tools.get_customer_profile(company_name)
    catalog_snapshot = tools.get_product_catalog_snapshot(product_ids) if product_ids else []
    related_products = tools.find_related_products(product_ids, limit=2) if product_ids else []
    system_prompt = ANSWER_BOT_PROMPT
    user_prompt = "\n".join(
        [
            f"Cliente: {company_name}",
            f"Resumen de solicitud: {project_summary or 'Sin resumen adicional'}",
            f"Servicios incluidos: {', '.join(product_names) or 'No disponible'}",
            f"Perfil cliente: {customer_profile}",
            f"Snapshot catalogo: {catalog_snapshot}",
            f"Lineas del presupuesto: {order_lines}",
            f"Referencia del presupuesto: {sale_order_id}",
            f"Importe total: {total} {currency}",
            f"Productos relacionados sugeridos: {related_products or 'Ninguno'}",
            (
                "Conceptos no resueltos: "
                + (", ".join(unmatched_requirements) if unmatched_requirements else "Ninguno")
            ),
            "Escribe una respuesta final lista para enviar en el chat.",
        ]
    )

    try:
        response = await deps.llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        reply_text = getattr(response, "content", "") or ""
    except Exception:
        related_names = [item.get("name", "").strip() for item in related_products if item]
        fallback_lines = [
            f"Hola {company_name},",
            "",
            "He generado un presupuesto inicial en Odoo con la informacion detectada en tu solicitud.",
            f"Referencia del presupuesto: {sale_order_id}",
            f"Importe total estimado: {total} {currency}",
        ]
        if product_names:
            fallback_lines.extend(
                [
                    "",
                    "Servicios incluidos:",
                    *[f"- {name}" for name in product_names],
                ]
            )
        if unmatched_requirements:
            fallback_lines.extend(
                [
                    "",
                    "Conceptos a revisar para afinar el alcance:",
                    *[f"- {item}" for item in unmatched_requirements],
                ]
            )
        if related_names:
            fallback_lines.extend(
                [
                    "",
                    "Como posible ampliacion futura, tambien podrian encajar:",
                    *[f"- {name}" for name in related_names],
                ]
            )
        fallback_lines.extend(
            [
                "",
                "Si quieres, puedo ayudarte a revisar el alcance funcional o recoger mas detalle para ajustar la propuesta.",
            ]
        )
        reply_text = "\n".join(fallback_lines)

    return {
        "messages": [AIMessage(content=reply_text.strip())],
    }

# nodo terminal de error: devuelve el error de forma controlada
# evita lanzar excepción y deja el resultado preparado para la capa superior
async def error_node(state: BudgetState) -> dict:
    error_msg = state.get("error", "Error desconocido en el agente de presupuestos")

    return {
        "messages": [
            AIMessage(content=f"No se ha podido crear el presupuesto: {error_msg}")
        ]
    }
