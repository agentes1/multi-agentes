import asyncio
import json

from langchain_core.messages import HumanMessage

from agents.budget_agent.graph import build_budget_graph
from agents.budget_agent.state import BudgetState
from agents.intake_agent.graph import build_intake_graph
from agents.intake_agent.state import IntakeState


async def run_intake_agent(source_input: dict) -> dict:
    intake_graph = build_intake_graph()

    intake_initial_state: IntakeState = {
        "messages": [HumanMessage(content="Analiza el mensaje del cliente")],
        "source_input": source_input,
        "extracted_text": "",
        "normalized_request": {},
        "validation_notes": [],
    }

    final_state = await intake_graph.ainvoke(intake_initial_state)
    return final_state


async def run_budget_agent(normalized_request: dict, thread_id: str) -> dict:
    budget_graph = build_budget_graph()

    budget_initial_state: BudgetState = {
        "messages": [
            HumanMessage(content="Genera un presupuesto a partir de la solicitud normalizada")
        ],
        "normalized_request": normalized_request,
        "selected_products": [],
        "retrieved_memory": {},
        "customer_profile": {},
        "quote_result": {},
        "final_text": "",
    }

    config = {"configurable": {"thread_id": thread_id}}

    final_state = await budget_graph.ainvoke(budget_initial_state, config=config)
    return final_state


async def main() -> None:
    # luego esto lo cambiamos por las API de entrada de datos: chat, email

    # 1. con error - implementar manejo de errores
    source_input = {
        "channel": "email",
        "from": "cliente@acme.com",
        "subject": "Automatización comercial",
        "body": (
            "Hola, somos una pequeña empresa que busca comprar unas nuevas sillas para la oficina, "
            " qué me podéis ofrecer? gracias"
        ),
    }

    # 2. con memoria
    source_input = {
        "channel": "email",
        "from": "cliente@acme.com",
        "subject": "Seguimos con el proceso",
        "body": ("Queremos retomar lo que hablamos y añadir presupuestos automáticos."),
    }

    print("\n=== EJECUTANDO INTAKE AGENT ===")
    intake_result = await run_intake_agent(source_input)

    normalized_request = intake_result["normalized_request"]
    validation_notes = intake_result["validation_notes"]

    print("\n=== NORMALIZED REQUEST ===\n")
    print(json.dumps(normalized_request, ensure_ascii=False, indent=2))

    print("\n=== VALIDATION NOTES ===\n")
    print(json.dumps(validation_notes, ensure_ascii=False, indent=2))

    print("\n=== EJECUTANDO BUDGET AGENT ===")
    budget_result = await run_budget_agent(
        normalized_request=normalized_request,
        thread_id="budget-acme-001",
    )

    print("\n=== QUOTE RESULT ===\n")
    print(json.dumps(budget_result["quote_result"], ensure_ascii=False, indent=2))

    print("\n=== PRESUPUESTO FINAL ===\n")
    print(budget_result["final_text"])


if __name__ == "__main__":
    asyncio.run(main())
