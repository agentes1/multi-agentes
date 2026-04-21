import pytest
from odoo.service import OdooService
from odoo.api import OdooAPIWrapper
from odoo.helpers import Table
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD


@pytest.fixture(scope="module")
def service():
    wrapper = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)
    return OdooService(wrapper)


# ── MUTACIONES ──────────────────────────────────────────────────────────────

def test_find_products_by_text_returns_list(service):
    results = service.find_products_by_text("CRM", limit=5)
    assert isinstance(results, list)
    for p in results:
        assert "id" in p
        assert "name" in p


def test_get_or_create_contact_creates_new(service):
    name = "_test_empresa_temp_borrar"
    partner_id = None
    try:
        partner_id = service.get_or_create_contact(name)
        assert isinstance(partner_id, int)
    finally:
        if partner_id:
            service._wrapper.delete(Table.Contact, [partner_id])


def test_get_or_create_contact_returns_existing_id(service):
    name = "_test_empresa_dedup"
    pid1 = None
    try:
        pid1 = service.get_or_create_contact(name)
        pid2 = service.get_or_create_contact(name)
        assert pid1 == pid2
    finally:
        if pid1:
            service._wrapper.delete(Table.Contact, [pid1])


def test_create_and_get_sale_order(service):
    partner_id = None
    order_id = None
    try:
        partner_id = service.get_or_create_contact("_test_cliente_orden_temp")
        order_id = service.create_sale_order(partner_id)
        assert isinstance(order_id, int)
        order = service.get_sale_order(order_id)
        assert "amount_total" in order
    finally:
        if order_id:
            # cancel before delete (Odoo requires cancellation before unlink)
            service._wrapper._query(Table.SaleOrder, "action_cancel", [[order_id]])
            service._wrapper.delete(Table.SaleOrder, [order_id])
        if partner_id:
            service._wrapper.delete(Table.Contact, [partner_id])


# ── CONSULTAS ────────────────────────────────────────────────────────────────

def test_search_products_returns_list(service):
    results = service.search_products("CRM")
    assert isinstance(results, list)


def test_get_product_by_code_returns_none_for_invalid(service):
    result = service.get_product_by_code("CODIGO_INEXISTENTE_XYZ")
    assert result is None


def test_list_catalog_returns_list(service):
    results = service.list_catalog()
    assert isinstance(results, list)


def test_find_client_returns_none_for_unknown(service):
    result = service.find_client("Empresa Que No Existe XYZ 9999")
    assert result is None


def test_list_client_orders_returns_list(service):
    results = service.list_client_orders(partner_id=1, limit=5)
    assert isinstance(results, list)


def test_list_client_tickets_returns_list(service):
    results = service.list_client_tickets(partner_id=1, limit=5)
    assert isinstance(results, list)
