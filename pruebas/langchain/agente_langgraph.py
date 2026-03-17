import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

# Resuelvo rutas absolutas a partir de la ubicación de este archivo.
# Así evito errores típicos cuando ejecuto el script desde otra carpeta.
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent
MCP_SERVER_PATH = PROJECT_ROOT / "mcp" / "mcp_servidor_precios.py"


class BudgetState(TypedDict):
    # Guardo los mensajes para poder inspeccionar la ejecución y dejar abierta
    # la posibilidad de ampliar esto luego a conversación multi-turno.
    messages: Annotated[list, add_messages]

    # Este es el JSON de entrada original.
    input_json: dict

    # Aquí guardo la versión normalizada de la solicitud.
    normalized_request: dict

    # Lista de productos del catálogo que vamos a presupuestar.
    selected_products: list[str]

    # Resultado estructurado que devuelve el MCP.
    quote_result: dict

    # Texto final del presupuesto redactado.
    final_text: str


# Uso Ollama en local.
# Temperatura 0 para que la prueba sea más estable y repetible.
llm = ChatOllama(
    model="llama3.1",
    temperature=0,
)


def map_requirements_to_products(requirements: list[str]) -> list[str]:
    # Este mapeo es simple a propósito para que la demo sea fácil de entender.
    # Mañana esto podría vivir en configuración, base de datos o incluso en Odoo.
    mapping = {
        "crm": "crm_base",
        "emails": "email_ai",
        "presupuestos": "quotation_ai",
        "odoo": "odoo_connector",
        "dashboard": "dashboard",
    }

    products = []
    for req in requirements:
        code = mapping.get(str(req).lower().strip())
        if code and code not in products:
            products.append(code)

    return products


async def intake_agent(state: BudgetState) -> dict:
    # Este primer agente interpreta el JSON y lo deja normalizado para el resto.
    payload = state["input_json"]

    prompt = f"""
Eres un agente comercial que analiza solicitudes para preparar presupuestos de automatización.

A partir del JSON de entrada, devuelve un JSON con esta estructura exacta:
{{
  "company_name": "...",
  "project_summary": "...",
  "requirements": ["crm", "emails", "presupuestos", "odoo", "dashboard"],
  "urgency": "baja|media|alta"
}}

Solo puedes usar esos valores de requirements si aplican.
Si algo no aparece claramente, no lo inventes.

JSON de entrada:
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    content = response.content if isinstance(response.content, str) else str(response.content)

    # Intento parsear directamente el JSON devuelto por el modelo.
    # Si no sale perfecto, hago un fallback para no bloquear la demo.
    try:
        normalized = json.loads(content)
    except Exception:
        normalized = {
            "company_name": payload.get("company_name", "Desconocido"),
            "project_summary": payload.get("summary", ""),
            "requirements": payload.get("requirements", []),
            "urgency": payload.get("urgency", "media"),
        }

    selected_products = map_requirements_to_products(normalized.get("requirements", []))

    return {
        "messages": [
            AIMessage(
                content=f"Solicitud normalizada: {json.dumps(normalized, ensure_ascii=False)}"
            )
        ],
        "normalized_request": normalized,
        "selected_products": selected_products,
    }


async def pricing_agent(state: BudgetState) -> dict:
    # Aquí conecto con el MCP usando ruta absoluta y el mismo intérprete Python
    # con el que estoy ejecutando este script. En Windows esto evita muchos fallos.
    if not MCP_SERVER_PATH.exists():
        raise FileNotFoundError(f"No encuentro el servidor MCP en esta ruta: {MCP_SERVER_PATH}")

    client = MultiServerMCPClient(
        {
            "odoo_budget": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(MCP_SERVER_PATH)],
            }
        }
    )

    # Abro una sesión con el servidor MCP y cargo sus tools.
    async with client.session("odoo_budget") as session:
        tools = await load_mcp_tools(session)
        tools_by_name = {tool.name: tool for tool in tools}

        company_name = state["normalized_request"].get("company_name", "Desconocido")
        selected_products = state.get("selected_products", [])

        customer_profile = await tools_by_name["get_customer_profile"].ainvoke(
            {"company_name": company_name}
        )

        quote = await tools_by_name["calculate_quote"].ainvoke(
            {
                "product_codes": selected_products,
                "company_name": company_name,
            }
        )

        final_prompt = f"""
Eres un agente de preventa.

Redacta un presupuesto claro y breve en español usando estos datos.

Solicitud normalizada:
{json.dumps(state["normalized_request"], ensure_ascii=False, indent=2)}

Perfil del cliente:
{json.dumps(customer_profile, ensure_ascii=False, indent=2)}

Resultado del presupuesto:
{json.dumps(quote, ensure_ascii=False, indent=2)}

Quiero una salida con:
- Resumen del proyecto
- Módulos incluidos
- Subtotal
- Descuento
- Total final
- Nota final indicando que el presupuesto es preliminar
"""

        final_response = await llm.ainvoke([HumanMessage(content=final_prompt)])
        final_text = (
            final_response.content
            if isinstance(final_response.content, str)
            else str(final_response.content)
        )

    return {
        "messages": [AIMessage(content=final_text)],
        "quote_result": quote,
        "final_text": final_text,
    }


def build_graph():
    # Monto un grafo mínimo con dos nodos.
    # El primero analiza la solicitud y el segundo consulta el MCP y compone el presupuesto.
    builder = StateGraph(BudgetState)

    builder.add_node("intake_agent", intake_agent)
    builder.add_node("pricing_agent", pricing_agent)

    builder.add_edge(START, "intake_agent")
    builder.add_edge("intake_agent", "pricing_agent")
    builder.add_edge("pricing_agent", END)

    # Esto me da memoria/checkpoints por thread_id.
    checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)


async def main():
    # Antes de ejecutar, valido la ruta del MCP para que el error sea claro.
    print(f"Proyecto raíz: {PROJECT_ROOT}")
    print(f"Servidor MCP: {MCP_SERVER_PATH}")

    if not MCP_SERVER_PATH.exists():
        raise FileNotFoundError(f"No existe el fichero del MCP en: {MCP_SERVER_PATH}")

    graph = build_graph()

    input_payload = {
        "company_name": "ACME",
        "summary": "Queremos automatizar la clasificación de emails, generar presupuestos y conectar el flujo comercial con Odoo",
        "requirements": ["emails", "presupuestos", "odoo", "crm"],
        "urgency": "alta",
    }

    initial_state: BudgetState = {
        "messages": [HumanMessage(content="Genera un presupuesto a partir del JSON recibido")],
        "input_json": input_payload,
        "normalized_request": {},
        "selected_products": [],
        "quote_result": {},
        "final_text": "",
    }

    config = {"configurable": {"thread_id": "demo-acme-001"}}

    # Muestro streaming de actualizaciones del grafo.
    async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):
        print("\n=== CHUNK ===")
        print(chunk)

    final_state = await graph.ainvoke(initial_state, config=config)

    print("\n=== PRESUPUESTO FINAL ===\n")
    print(final_state["final_text"])


if __name__ == "__main__":
    asyncio.run(main())
