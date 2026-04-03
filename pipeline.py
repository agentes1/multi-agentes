# pipeline.py
# orquestador principal: recibe un input crudo, lo pasa por los dos agentes en secuencia

from agents.budget_agent.dependencies import build_dependencies as build_budget_deps
from agents.budget_agent.graph import build_budget_graph
from agents.intake_agent.dependencies import build_dependencies as build_intake_deps
from agents.intake_agent.graph import build_intake_graph


async def run_pipeline(source_input: dict, thread_id: str | None, model: str | None = None) -> dict:
    # paso 1: intake_agent transforma la entrada cruda en solicitud normalizada
    intake_result = await build_intake_graph().ainvoke(
        {"source_input": source_input},
        config={"configurable": {"deps": build_intake_deps(model=model)}},
    )

    if intake_result.get("error"):
        return {"ok": False, "error": intake_result["error"]}

    # paso 2: budget_agent convierte la solicitud en presupuesto
    budget_result = await build_budget_graph().ainvoke(
        {"normalized_request": intake_result["normalized_request"]},
        config={
            "configurable": {
                "deps": build_budget_deps(model=model),
                "thread_id": thread_id,  # requerido por InMemorySaver
            }
        },
    )

    if budget_result.get("error"):
        return {"ok": False, "error": budget_result["error"]}

    return {
        "ok": True,
        "normalized_request": intake_result["normalized_request"],
        "quote_result": budget_result["quote_result"],
        "final_text": budget_result["final_text"],
    }
