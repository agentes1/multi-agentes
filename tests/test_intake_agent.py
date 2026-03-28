# tests/test_intake_agent.py
import pytest

from agents.intake_agent.dependencies import IntakeDependencies
from agents.intake_agent.graph import build_intake_graph

# --- mocks ---


class MockLLMValid:
    """Simula un LLM que devuelve un JSON bien formado."""

    async def ainvoke(self, messages):
        class Response:
            content = """{
                "company_name": "Acme SL",
                "project_summary": "Necesitan CRM y facturación",
                "requirements": ["crm", "presupuestos"],
                "urgency": "alta",
                "missing_information": []
            }"""

        return Response()


class MockLLMInvalidJSON:
    """Simula un LLM que devuelve texto libre en lugar de JSON."""

    async def ainvoke(self, messages):
        class Response:
            content = "Aquí tienes el resumen del cliente, necesita un CRM..."

        return Response()


def _build_deps(llm) -> IntakeDependencies:
    return IntakeDependencies(llm=llm)


def _base_config(deps: IntakeDependencies) -> dict:
    return {"configurable": {"deps": deps}}


# --- tests ---


@pytest.mark.asyncio
async def test_flujo_completo_email_valido():
    """Un email con asunto y cuerpo debe producir un normalized_request completo."""
    graph = build_intake_graph()
    deps = _build_deps(MockLLMValid())

    result = await graph.ainvoke(
        {
            "source_input": {
                "channel": "email",
                "from": "cliente@acme.com",
                "subject": "Solicitud de presupuesto ERP",
                "body": "Hola, somos Acme SL y necesitamos un CRM y módulo de facturación.",
            }
        },
        config=_base_config(deps),
    )

    assert result["error"] is None
    assert result["normalized_request"]["company_name"] == "Acme SL"
    assert "crm" in result["normalized_request"]["requirements"]


@pytest.mark.asyncio
async def test_error_email_sin_contenido():
    """Un email sin asunto ni cuerpo debe terminar en error_node."""
    graph = build_intake_graph()
    deps = _build_deps(MockLLMValid())

    result = await graph.ainvoke(
        {
            "source_input": {
                "channel": "email",
                "from": "cliente@acme.com",
                "subject": "",
                "body": "",
            }
        },
        config=_base_config(deps),
    )

    assert result["error"] is not None
    assert "email" in result["error"].lower()
    assert result["normalized_request"] == {}


@pytest.mark.asyncio
async def test_error_llm_devuelve_json_invalido():
    """Si el LLM no devuelve JSON válido debe terminar en error_node."""
    graph = build_intake_graph()
    deps = _build_deps(MockLLMInvalidJSON())

    result = await graph.ainvoke(
        {
            "source_input": {
                "channel": "chat",
                "user_name": "Juan",
                "company_name": "Acme SL",
                "message": "Queremos un CRM integrado con Odoo.",
            }
        },
        config=_base_config(deps),
    )

    assert result["error"] is not None
    assert "json" in result["error"].lower()
    assert result["normalized_request"] == {}
