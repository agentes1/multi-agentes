from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.state import BudgetState


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

            matches = deps.odoo_wrapper.find_products_by_text(value, limit=5)

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

    normalized_request = state["normalized_request"]
    company_name = normalized_request.get("company_name", "Desconocido")

    try:
        partner_id = deps.odoo_wrapper.get_or_create_contact(company_name)
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

    normalized_request = state["normalized_request"]
    company_name = normalized_request.get("company_name", "Desconocido")
    selected_products = state.get("selected_products", [])
    partner_id = state["partner_id"]

    try:
        # crea la cabecera del presupuesto
        sale_order_id = deps.odoo_wrapper.create_sale_order(partner_id=partner_id)

        # añade líneas al presupuesto usando directamente los productos ya resueltos desde Odoo
        for product in selected_products:
            deps.odoo_wrapper.create_sale_order_line(
                order_id=sale_order_id,
                product_id=product["id"],
                quantity=1,
            )

        # lee el presupuesto ya creado para devolver un resumen útil
        order = deps.odoo_wrapper.get_sale_order(sale_order_id)

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

# nodo terminal de error: devuelve el error de forma controlada
# evita lanzar excepción y deja el resultado preparado para la capa superior
async def error_node(state: BudgetState) -> dict:
    error_msg = state.get("error", "Error desconocido en el agente de presupuestos")

    return {
        "messages": [
            AIMessage(content=f"No se ha podido crear el presupuesto: {error_msg}")
        ]
    }