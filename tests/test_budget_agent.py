import uuid

import pytest

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.graph import build_budget_graph
from odoo.api import OdooAPIWrapper
from odoo.service import OdooService
from odoo.helpers import Table
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME


class MockLLM:
    """Mock LLM that returns no tool calls — lets enrich_context_node skip enrichment."""

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        class _Response:
            content = ""
            tool_calls = []
        return _Response()


def _build_deps() -> BudgetDependencies:
    wrapper = OdooAPIWrapper(
        url=ODOO_BASE_URL,
        username=ODOO_USERNAME,
        password=ODOO_PASSWORD,
        db=ODOO_DB,
    )
    return BudgetDependencies(
        llm=MockLLM(),
        odoo_service=OdooService(wrapper),
    )


def _base_config(deps: BudgetDependencies) -> dict:
    return {
        "configurable": {
            "deps": deps,
            "thread_id": f"test-budget-agent-{uuid.uuid4()}",
        }
    }


def _cleanup(deps: BudgetDependencies, sale_order_id: int | None, company_name: str | None) -> None:
    if sale_order_id:
        try:
            deps.odoo_service._wrapper._query(Table.SaleOrder, "action_cancel", [[sale_order_id]])
            deps.odoo_service._wrapper.delete(Table.SaleOrder, [sale_order_id])
        except Exception:
            pass
    if company_name:
        try:
            partner = deps.odoo_service.find_client(company_name)
            if partner:
                deps.odoo_service._wrapper.delete(Table.Contact, [partner["id"]])
        except Exception:
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_json_crea_presupuesto_real_en_odoo():
    graph = build_budget_graph()
    deps = _build_deps()
    company_name = "Acme Presupuestos SL"

    result = await graph.ainvoke(
        {
            "normalized_request": {
                "company_name": company_name,
                "project_summary": "Implantación básica para soporte y ventas",
                "requirements": ["helpdesk", "crm"],
                "urgency": "media",
            }
        },
        config=_base_config(deps),
    )

    sale_order_id = result.get("sale_order_id")

    try:
        assert result.get("error") is None
        assert sale_order_id is not None
        assert isinstance(sale_order_id, int)

        summary = result["quote_summary"]
        assert summary["company_name"] == company_name
        assert summary["sale_order_id"] == sale_order_id
        assert isinstance(summary["subtotal"], float)
        assert isinstance(summary["total"], float)
        assert summary["currency"] == "EUR"

        order = deps.odoo_service.get_sale_order(sale_order_id)
        assert order.get("id") == sale_order_id or "amount_total" in order
    finally:
        _cleanup(deps, sale_order_id, company_name)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_json_con_varios_requisitos_crea_presupuesto_en_odoo():
    graph = build_budget_graph()
    deps = _build_deps()
    company_name = "Beta Industrial SL"

    result = await graph.ainvoke(
        {
            "normalized_request": {
                "company_name": company_name,
                "project_summary": "Proyecto con varias áreas funcionales",
                "requirements": ["crm", "sales", "helpdesk"],
                "urgency": "alta",
            }
        },
        config=_base_config(deps),
    )

    sale_order_id = result.get("sale_order_id")

    try:
        assert result.get("error") is None
        assert sale_order_id is not None

        selected_products = result["selected_products"]
        assert isinstance(selected_products, list)
        assert len(selected_products) >= 1

        summary = result["quote_summary"]
        assert summary["sale_order_id"] == sale_order_id
        assert summary["company_name"] == company_name
        assert summary["total"] >= 0
    finally:
        _cleanup(deps, sale_order_id, company_name)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_json_cliente_nuevo_crea_partner_y_presupuesto():
    graph = build_budget_graph()
    deps = _build_deps()
    company_name = "Cliente Nuevo Presupuesto Test SL"

    result = await graph.ainvoke(
        {
            "normalized_request": {
                "company_name": company_name,
                "project_summary": "Nueva implantación Odoo",
                "requirements": ["crm"],
                "urgency": "baja",
            }
        },
        config=_base_config(deps),
    )

    sale_order_id = result.get("sale_order_id")

    try:
        assert result.get("error") is None
        assert sale_order_id is not None

        partner = deps.odoo_service.find_client(company_name)
        assert partner is not None
        assert company_name.lower() in partner["name"].lower()

        order = deps.odoo_service.get_sale_order(sale_order_id)
        assert "amount_total" in order
    finally:
        _cleanup(deps, sale_order_id, company_name)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_json_sin_requisitos_devuelve_error_y_no_crea_presupuesto():
    graph = build_budget_graph()
    deps = _build_deps()

    result = await graph.ainvoke(
        {
            "normalized_request": {
                "company_name": "Empresa Sin Requisitos SL",
                "project_summary": "Solicitud vacía",
                "requirements": [],
                "urgency": "media",
            }
        },
        config=_base_config(deps),
    )

    assert result.get("error") is not None
    assert "no contiene requisitos" in result["error"].lower()
    assert result.get("sale_order_id") is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_json_con_requisitos_no_mapeables_devuelve_error():
    graph = build_budget_graph()
    deps = _build_deps()

    result = await graph.ainvoke(
        {
            "normalized_request": {
                "company_name": "Empresa Requisitos Raros SL",
                "project_summary": "Caso de requisitos desconocidos",
                "requirements": ["bloquechain_cuantica", "modulo_imposible"],
                "urgency": "alta",
            }
        },
        config=_base_config(deps),
    )

    assert result.get("error") is not None
    assert "no se encontraron productos" in result["error"].lower()
    assert result.get("sale_order_id") is None
