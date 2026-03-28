import json

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.state import BudgetState
from schemas.budget import QuoteLine, QuoteResult, StoredQuoteMemory
from shared.catalog import map_requirements_to_products


# helper para obtener dependencias inyectadas desde el config del grafo
def _get_deps(config: RunnableConfig) -> BudgetDependencies:
    deps = config.get("configurable", {}).get("deps")
    if deps is None:
        raise RuntimeError("BudgetDependencies no inyectadas en config")
    return deps


# prepara el presupuesto obteniendo los productos del json normalizado por el agente anterior
# error si no hay requisitos o no se mapean a productos conocidos
async def prepare_budget_node(state: BudgetState, config: RunnableConfig) -> dict:
    normalized_request = state["normalized_request"]
    requirements = normalized_request.get("requirements", [])

    # validación: la solicitud debe contener requisitos
    if not requirements:
        return {
            "error": "La solicitud no contiene requisitos. No se puede generar presupuesto.",
            "selected_products": [],
        }

    selected_products = map_requirements_to_products(requirements)

    # validación: los requisitos deben mapearse a productos del catálogo
    if not selected_products:
        return {
            "error": (
                f"No se encontraron productos presupuestables para los requisitos: {requirements}"
            ),
            "selected_products": [],
        }

    return {
        "messages": [
            AIMessage(
                content=f"Solicitud preparada para presupuesto con productos {selected_products}"
            )
        ],
        "selected_products": selected_products,
        "error": None,
    }


# recupera el histórico previo del cliente para contexto comercial
async def retrieve_memory_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)

    normalized_request = state["normalized_request"]
    company_name = normalized_request.get("company_name", "Desconocido")

    # obtenemos último contexto comercial del cliente desde el store
    retrieved = deps.memory_store.get_last_quote_memory(company_name)

    return {
        "messages": [
            AIMessage(
                content=(
                    f"Memoria recuperada de {company_name}: "
                    f"presupuestos previos={retrieved.quote_count}, "
                    f"último total={retrieved.last_quote_total}"
                )
            )
        ],
        "retrieved_memory": retrieved.model_dump(),
    }


# calcula el presupuesto llamando al servicio MCP y construye el QuoteResult estructurado
# error si el servicio MCP falla
async def pricing_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)

    normalized_request = state["normalized_request"]
    company_name = normalized_request.get("company_name", "Desconocido")
    selected_products = state.get("selected_products", [])
    retrieved_memory = state.get("retrieved_memory", {})

    # llamada al servicio MCP: obtiene perfil del cliente y cálculo bruto del presupuesto
    try:
        budget_context = await deps.mcp_service.get_budget_context(
            company_name=company_name,
            product_codes=selected_products,
        )
    except Exception as e:
        return {
            "error": f"Error al obtener presupuesto del servicio MCP: {e}",
        }

    # desempaqueta respuesta del servicio
    customer_profile = budget_context["customer_profile"]
    raw_quote = budget_context["quote"]

    # enriquecemos el presupuesto bruto con versión e histórico
    raw_quote["version"] = int(retrieved_memory.get("quote_count", 0)) + 1
    raw_quote["based_on_previous_quote"] = retrieved_memory.get("quote_count", 0) > 0

    # transformamos cada línea de formato MCP a QuoteLine
    adapted_lines = []
    for line in raw_quote.get("lines", []):
        unit_price = float(line.get("unit_price", 0))
        quantity = int(line.get("quantity", 1))

        adapted_lines.append(
            QuoteLine(
                product_code=line.get("code", ""),
                description=line.get("name", ""),
                unit_price=unit_price,
                quantity=quantity,
                line_total=round(unit_price * quantity, 2),
            )
        )

    quote_result = QuoteResult(
        company_name=raw_quote.get("company_name", company_name),
        lines=adapted_lines,
        subtotal=float(raw_quote.get("subtotal", 0)),
        discount=float(raw_quote.get("discount_amount", 0)),
        total=float(raw_quote.get("total", 0)),
        currency=raw_quote.get("currency", "EUR"),
        warnings=raw_quote.get("warnings", []),
        version=int(raw_quote.get("version", 1)),
        based_on_previous_quote=bool(raw_quote.get("based_on_previous_quote", False)),
    )

    return {
        "messages": [
            AIMessage(
                content=(
                    f"Presupuesto calculado para {company_name}. "
                    f"Total={quote_result.total} {quote_result.currency}, "
                    f"versión={quote_result.version}"
                )
            )
        ],
        "customer_profile": customer_profile,
        "quote_result": quote_result.model_dump(),
        "error": None,
    }


# redacta el presupuesto en lenguaje natural usando el LLM
# → más adelante sustituir por formato de presupuesto Odoo
async def render_quote_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)

    normalized_request = state["normalized_request"]
    customer_profile = state["customer_profile"]
    quote_result = state["quote_result"]
    retrieved_memory = state["retrieved_memory"]

    prompt = f"""
Eres un agente de preventa.

Redacta un presupuesto profesional, breve y claro en español.

Solicitud normalizada:
{json.dumps(normalized_request, ensure_ascii=False, indent=2)}

Perfil del cliente:
{json.dumps(customer_profile, ensure_ascii=False, indent=2)}

Histórico previo:
{json.dumps(retrieved_memory, ensure_ascii=False, indent=2)}

Resultado estructurado del presupuesto:
{json.dumps(quote_result, ensure_ascii=False, indent=2)}

Quiero una salida con:
- Título
- Resumen del proyecto
- Módulos incluidos
- Subtotal
- Descuento
- Total final
- Nota final indicando que el presupuesto es preliminar
- Si existe histórico previo, menciona de forma breve que se ha tenido en cuenta

No inventes importes. Usa exactamente los importes dados.
"""

    response = await deps.llm.ainvoke([HumanMessage(content=prompt)])
    # aseguramos que el contenido es siempre string
    final_text = response.content if isinstance(response.content, str) else str(response.content)

    return {
        "messages": [AIMessage(content=final_text)],
        "final_text": final_text,
    }


# guarda el presupuesto completo en memoria persistente
# se ejecuta después de render_quote_node para tener el final_text real
async def persist_memory_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)

    normalized_request = state["normalized_request"]

    # construimos el objeto completo con el texto final ya generado
    item = StoredQuoteMemory(
        company_name=normalized_request.get("company_name", "Desconocido"),
        normalized_request=normalized_request,
        selected_products=state["selected_products"],
        quote_result=state["quote_result"],
        final_text=state["final_text"],
        timestamp=deps.memory_store.now_iso(),
    )

    deps.memory_store.append_quote(item)

    return {
        "messages": [
            AIMessage(content=f"Histórico actualizado para {item.company_name} en {item.timestamp}")
        ]
    }


# nodo terminal de error: se alcanza cuando prepare o pricing detectan un fallo
# devuelve un final_text descriptivo en lugar de lanzar excepción
async def error_node(state: BudgetState) -> dict:
    error_msg = state.get("error", "Error desconocido en el agente de presupuestos")

    return {
        "messages": [AIMessage(content=f"No se ha podido generar el presupuesto: {error_msg}")],
        "final_text": f"Error: {error_msg}",
    }
