import asyncio
from agents.rag_agent.graph import build_rag_graph
from agents.rag_agent.dependencies import build_dependencies

async def main():
    graph = build_rag_graph()
    deps = build_dependencies()

    result = await graph.ainvoke(
        {"input_text": "No puedo acceder al módulo de ventas"},
        config={"configurable": {"deps": deps}},
    )

    print("Respuesta:", result.get("reply_text"))
    print("Tickets recuperados:", len(result.get("retrieved_tickets", [])))

asyncio.run(main())