import asyncio
import json

from langchain_core.messages import HumanMessage

from agents.intake_agent.graph import build_intake_graph
from agents.intake_agent.state import IntakeState


async def main() -> None:
    graph = build_intake_graph()

    input_payload = {
        "channel": "email",
        "from": "cliente@acme.com",
        "subject": "Automatización comercial y presupuestos",
        "body": (
            "Hola, somos ACME. Queremos automatizar la clasificación de emails, "
            "la generación de presupuestos y conectar el flujo comercial con Odoo. "
            "Nos gustaría empezar pronto porque tenemos bastante urgencia."
        ),
    }

    initial_state: IntakeState = {
        "messages": [HumanMessage(content="Analiza el mensaje del cliente")],
        "source_input": input_payload,
        "extracted_text": "",
        "normalized_request": {},
        "validation_notes": [],
    }

    async for chunk in graph.astream(initial_state, stream_mode="updates"):
        print("\n=== CHUNK ===")
        print(json.dumps(chunk, ensure_ascii=False, indent=2, default=str))

    final_state = await graph.ainvoke(initial_state)

    print("\n=== NORMALIZED REQUEST ===\n")
    print(json.dumps(final_state["normalized_request"], ensure_ascii=False, indent=2))

    print("\n=== VALIDATION NOTES ===\n")
    print(json.dumps(final_state["validation_notes"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
