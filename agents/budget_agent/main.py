import asyncio
import json

from langchain_core.messages import HumanMessage

from agents.budget_agent.graph import build_budget_graph
from agents.budget_agent.state import BudgetState
from shared.config import MCP_SERVER_PATH


async def main() -> None:
    print(f"Servidor MCP: {MCP_SERVER_PATH}")

    if not MCP_SERVER_PATH.exists():
        raise FileNotFoundError(f"No existe el fichero del MCP en: {MCP_SERVER_PATH}")

    # construimos grafo
    graph = build_budget_graph()

    # inputs - ejemplo
    input_payload = {
        "company_name": "ACME",
        "summary": "Queremos automatizar la clasificación de emails, generar presupuestos y conectar el flujo comercial con Odoo",
        "requirements": ["emails", "presupuestos", "odoo", "crm"],
        "urgency": "alta",
    }

    # estado inicial
    initial_state: BudgetState = {
        "messages": [HumanMessage(content="Genera un presupuesto a partir del JSON recibido")],
        "input_json": input_payload,
        "normalized_request": {},
        "selected_products": [],
        "retrieved_memory": {},
        "customer_profile": {},
        "quote_result": {},
        "final_text": "",
    }

    config = {"configurable": {"thread_id": "budget-acme-001"}}

    # streaming - imprimimos updates
    async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):
        print("\n=== CHUNK ===")
        print(json.dumps(chunk, ensure_ascii=False, indent=2, default=str))

    # obtenemos estado final, cuando ya se acaba el flujo
    final_state = await graph.ainvoke(initial_state, config=config)

    print("\n=== QUOTE RESULT ===\n")
    print(json.dumps(final_state["quote_result"], ensure_ascii=False, indent=2))

    print("\n=== PRESUPUESTO FINAL ===\n")
    print(final_state["final_text"])


if __name__ == "__main__":
    asyncio.run(main())
