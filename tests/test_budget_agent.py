import uuid

import pytest

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.graph import build_budget_graph
from odoo.api_wrapper import OdooAPIWrapper
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME


def _build_deps() -> BudgetDependencies:
    return BudgetDependencies(
        odoo_wrapper=OdooAPIWrapper(
            url=ODOO_BASE_URL,
            username=ODOO_USERNAME,
            password=ODOO_PASSWORD,
            db=ODOO_DB,
        ),
    )


def _base_config(deps: BudgetDependencies) -> dict:
    return {
        "configurable": {
            "deps": deps,
            "thread_id": f"test-budget-agent-{uuid.uuid4()}",
        }
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_json_crea_presupuesto_real_en_odoo():
    graph = build_budget_graph()
    deps = _build_deps()

    result = await graph.ainvoke(
        {
            "normalized_request": {
                "company_name": "Acme Presupuestos SL",
                "project_summary": "Implantación básica para soporte y ventas",
                "requirements": ["helpdesk", "crm"],
                "urgency": "media",
            }
        },
        config=_base_config(deps),
    )

    sale_order_id = result.get("sale_order_id")

    try:
        assert result["error"] is None
        assert sale_order_id is not None
        assert isinstance(sale_order_id, int)

        assert result["normalized_request"]["company_name"] == "Acme Presupuestos SL"
        assert "helpdesk" in result["normalized_request"]["requirements"]
        assert "crm" in result["normalized_request"]["requirements"]

        assert isinstance(result["selected_products"][0], dict)
        assert "id" in result["selected_products"][0]

        summary = result["quote_summary"]
        assert summary["company_name"] == "Acme Presupuestos SL"
        assert summary["sale_order_id"] == sale_order_id
        assert isinstance(summary["subtotal"], float)
        assert isinstance(summary["total"], float)
        assert summary["currency"] == "EUR"

        order = deps.odoo_wrapper.get_sale_order(sale_order_id)
        assert order is not None
        assert order["id"] == sale_order_id
        assert order["partner_id"]
        assert order["amount_total"] >= 0

    finally:
        if sale_order_id:
            print("fin")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_json_con_varios_requisitos_crea_presupuesto_en_odoo():
    graph = build_budget_graph()
    deps = _build_deps()

    result = await graph.ainvoke(
        {
            "normalized_request": {
                "company_name": "Beta Industrial SL",
                "project_summary": "Proyecto con varias áreas funcionales",
                "requirements": ["crm", "sales", "helpdesk"],
                "urgency": "alta",
            }
        },
        config=_base_config(deps),
    )

    sale_order_id = result.get("sale_order_id")

    try:
        assert result["error"] is None
        assert sale_order_id is not None

        selected_products = result["selected_products"]
        assert isinstance(selected_products, list)
        assert len(selected_products) >= 1

        summary = result["quote_summary"]
        assert summary["sale_order_id"] == sale_order_id
        assert summary["company_name"] == "Beta Industrial SL"
        assert summary["total"] >= 0

        order = deps.odoo_wrapper.get_sale_order(sale_order_id)
        assert order is not None
        assert order["id"] == sale_order_id

    finally:
        if sale_order_id:
            print("fin")


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
        assert result["error"] is None
        assert sale_order_id is not None

        partners = deps.odoo_wrapper.search_read(
            "res.partner",
            [("name", "=", company_name)],
            fields=["id", "name"],
            limit=10,
        )

        assert partners
        assert any(p["name"] == company_name for p in partners)

        order = deps.odoo_wrapper.get_sale_order(sale_order_id)
        assert order is not None
        assert order["id"] == sale_order_id

    finally:
        if sale_order_id:
            print("fin")


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

    assert result["error"] is not None
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

    assert result["error"] is not None
    assert "no se encontraron productos presupuestables" in result["error"].lower()
    assert result.get("sale_order_id") is None