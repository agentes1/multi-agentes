# tests/test_budget_agent_errors.py
import pytest

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.graph import build_budget_graph

# --- mocks ---


class MockLLM:
    async def ainvoke(self, messages):
        class Response:
            content = "Presupuesto de prueba generado."

        return Response()


class MockMemoryStore:
    def get_last_quote_memory(self, company_name):
        # devuelve objeto mínimo con los campos que usa retrieve_memory_node
        class Memory:
            quote_count = 0
            last_quote_total = 0.0

            def model_dump(self):
                return {"quote_count": 0, "last_quote_total": 0.0}

        return Memory()

    def append_quote(self, item):
        pass

    def now_iso(self):
        return "2025-01-01T00:00:00"


class MockMCPService:
    async def get_budget_context(self, company_name, product_codes):
        return {
            "customer_profile": {"name": company_name, "discount": 0},
            "quote": {
                "company_name": company_name,
                "lines": [],
                "subtotal": 0.0,
                "discount_amount": 0.0,
                "total": 0.0,
                "currency": "EUR",
                "warnings": [],
            },
        }


class MockMCPServiceFailing:
    # simula un MCP que lanza excepción
    async def get_budget_context(self, company_name, product_codes):
        raise ConnectionError("Servicio MCP no disponible")


def _build_deps(mcp_service=None) -> BudgetDependencies:
    return BudgetDependencies(
        llm=MockLLM(),
        memory_store=MockMemoryStore(),
        mcp_service=mcp_service or MockMCPService(),
    )


def _base_config(deps: BudgetDependencies) -> dict:
    # thread_id requerido por InMemorySaver para identificar la sesión
    return {"configurable": {"deps": deps, "thread_id": "test-thread"}}


# --- tests ---


@pytest.mark.asyncio
async def test_error_cuando_requirements_vacio():
    """Si normalized_request no tiene requirements, el grafo debe terminar con error."""
    graph = build_budget_graph()
    deps = _build_deps()

    result = await graph.ainvoke(
        {
            "normalized_request": {
                "company_name": "Empresa Test",
                "requirements": [],  # vacío → debe fallar en prepare_budget_node
            }
        },
        config=_base_config(deps),
    )

    assert result["error"] is not None
    assert "requisitos" in result["error"].lower()
    assert result["final_text"].startswith("Error:")


@pytest.mark.asyncio
async def test_error_cuando_mcp_falla():
    """Si el servicio MCP lanza excepción, el grafo debe terminar con error."""
    graph = build_budget_graph()
    # inyectamos el MCP que falla y un catálogo que sí devuelve productos
    deps = _build_deps(mcp_service=MockMCPServiceFailing())

    result = await graph.ainvoke(
        {
            "normalized_request": {
                "company_name": "Empresa Test",
                "requirements": ["crm", "facturacion"],  # requisitos válidos
            }
        },
        config=_base_config(deps),
    )

    assert result["error"] is not None
    assert "mcp" in result["error"].lower()
    assert result["final_text"].startswith("Error:")
