import json

from langchain_core.messages import AIMessage, HumanMessage

from agents.budget_agent.state import BudgetState
from schemas.budget import QuoteLine, QuoteResult, StoredQuoteMemory
from services.mcp_budget import MCPBudgetService
from shared.catalog import map_requirements_to_products
from shared.llm import get_llm
from shared.memory_store import QuoteMemoryStore

llm = get_llm()
memory_store = QuoteMemoryStore()
mcp_service = MCPBudgetService()


# preparamos budget obteniendo los productos del json normalizado por el anterior agente
async def prepare_budget_node(state: BudgetState) -> dict:
    normalized_request = state["normalized_request"]
    requirements = normalized_request.get("requirements", [])

    selected_products = map_requirements_to_products(requirements)

    return {
        "messages": [
            AIMessage(
                content=(f"Solicitud preparada para presupuesto con productos {selected_products}")
            )
        ],
        "selected_products": selected_products,
    }


# nodo recuperación histórico previo
async def retrieve_memory_node(state: BudgetState) -> dict:
    # lee solicitud normalizada y obtiene el nombre de la empresa
    normalized_request = state["normalized_request"]
    company_name = normalized_request.get("company_name", "Desconocido")

    retrieved = memory_store.get_last_quote_memory(
        company_name
    )  # obtenemos último contexto comercial del cliente

    # guardamos un mensaje de traza y la memoria recuperada
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


# nodo que calcula el presupuesto
async def pricing_node(state: BudgetState) -> dict:
    # obtenemos datos necesarios
    normalized_request = state["normalized_request"]
    company_name = normalized_request.get("company_name", "Desconocido")
    selected_products = state.get("selected_products", [])
    retrieved_memory = state.get("retrieved_memory", {})

    warnings = []  # lista problemas no bloqueantes

    if not selected_products:
        warnings.append("No se han detectado productos presupuestables a partir de la solicitud")

    # pide al servicio MCP el perfil del cliente y cálculo bruto del presupuesto
    budget_context = await mcp_service.get_budget_context(
        company_name=company_name,
        product_codes=selected_products,
    )

    # desempaqueta respuesta del servicio
    customer_profile = budget_context["customer_profile"]
    raw_quote = budget_context["quote"]

    raw_quote["warnings"] = list(set(raw_quote.get("warnings", []) + warnings))
    raw_quote["version"] = (
        int(retrieved_memory.get("quote_count", 0)) + 1
    )  # versión de presupuesto - cantindad de presupuestos previos
    raw_quote["based_on_previous_quote"] = (
        retrieved_memory.get("quote_count", 0) > 0
    )  # ¿se ha generado teniendo histórico previo?

    adapted_lines = []
    for line in raw_quote.get("lines", []):
        # transformando a float e int respectivamente
        unit_price = float(line.get("unit_price", 0))
        quantity = int(line.get("quantity", 1))

        # trasnformando de formato MCP a QuoteLine
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

    # guardamos en el estado traza del cálculo, perfil del cliente, resultado estructurado
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
    }


# nodo que guarda el presupuesto en memoria persistente
async def persist_memory_node(state: BudgetState) -> dict:
    # leemos estado de la información que queremos guardar
    normalized_request = state["normalized_request"]
    quote_result = state["quote_result"]
    selected_products = state["selected_products"]

    # objeto que se guardará en el histórico
    item = StoredQuoteMemory(
        company_name=normalized_request.get("company_name", "Desconocido"),
        normalized_request=normalized_request,
        selected_products=selected_products,
        quote_result=quote_result,
        final_text="",
        timestamp=memory_store.now_iso(),
    )

    # guardamos nuevo presupuesto en almacenamiento
    memory_store.append_quote(item)

    # traza indicando que el histórico se ha actualizado
    return {
        "messages": [
            AIMessage(
                content=(f"Histórico actualizado para {item.company_name} en {item.timestamp}")
            )
        ]
    }


# nodo redacta presupuesto en lenguaje natural -> más tarde cambiar a formato presupuesto Odoo
async def render_quote_node(state: BudgetState) -> dict:
    # lee información relevante
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

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    final_text = response.content if isinstance(response.content, str) else str(response.content)

    return {
        "messages": [AIMessage(content=final_text)],
        "final_text": final_text,
    }
