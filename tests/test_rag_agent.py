import pytest
from agents.rag_agent.graph import build_rag_graph
from agents.rag_agent.dependencies import build_dependencies


@pytest.fixture
def graph():
    return build_rag_graph()


@pytest.fixture
def deps():
    return build_dependencies()


@pytest.mark.asyncio
async def test_rag_finds_similar_ticket(graph, deps):
    """Si la consulta coincide con un ticket, se recuperan resultados."""
    result = await graph.ainvoke(
        {"input_text": "no puedo acceder al módulo de ventas"},
        config={"configurable": {"deps": deps}},
    )
    assert len(result.get("retrieved_tickets", [])) > 0
    assert result.get("reply_text", "") != ""


@pytest.mark.asyncio
async def test_rag_fallback_on_no_match(graph, deps):
    """Si no hay tickets similares, devuelve el mensaje de fallback."""
    result = await graph.ainvoke(
        {"input_text": "xyz123 consulta sin sentido zzz"},
        config={"configurable": {"deps": deps}},
    )
    assert result.get("retrieved_tickets", []) == []
    assert "No he encontrado" in result.get("reply_text", "")


@pytest.mark.asyncio
async def test_rag_empty_input(graph, deps):
    """Con input vacío el agente no rompe."""
    result = await graph.ainvoke(
        {"input_text": ""},
        config={"configurable": {"deps": deps}},
    )
    assert result.get("reply_text", "") != ""