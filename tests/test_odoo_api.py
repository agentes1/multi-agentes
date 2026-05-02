import pytest
from odoo.api import OdooAPI, Table
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD

@pytest.fixture(scope="module")
def api():
    return OdooAPI(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)


def test_get_dbs(api):
    dbs = api.get_dbs()
    assert isinstance(dbs, list)
    assert ODOO_DB in dbs


def test_create_read_delete_product(api):
    # Create
    product_data = [{'name': 'Test API Product', 'type': 'service'}]
    product_ids = api.create(Table.Product, product_data)
    assert isinstance(product_ids, list)
    assert len(product_ids) == 1
    pid = product_ids[0]

    # Read by ID
    products = api.get_by_id(Table.Product, [pid], fields=['name'])
    assert products is not None
    assert len(products) == 1
    assert products[0]['name'] == 'Test API Product'

    # Delete
    res = api.delete(Table.Product, [pid])
    assert res is True

    # Verify deleted
    products = api.get_by_id(Table.Product, [pid])
    assert products is None 


def test_get_all_products(api):
    # Just check if we can list products
    products = api.get_all(Table.Product, fields=['name'], limit=5)
    assert isinstance(products, list)
    assert len(products) <= 5


def test_get_by_value_product(api):
    # Create a product with a unique code
    code = 'UNIQUE_CODE_123'
    pid = api.create(Table.Product, [{'name': 'Unique Product', 'default_code': code}])[0]
    
    try:
        # Exact search
        results = api.get_by_value(Table.Product, {'default_code': code}, fields=['name'], exact=True)
        assert results is not None
        assert len(results) == 1
        assert results[0]['name'] == 'Unique Product'

        # ilike search
        results = api.get_by_value(Table.Product, {'default_code': 'UNIQUE_CODE'}, fields=['name'], exact=False)
        assert results is not None
        assert any(r['name'] == 'Unique Product' for r in results)
    finally:
        api.delete(Table.Product, [pid])


def test_update_product(api):
    pid = api.create(Table.Product, [{'name': 'Before Update'}])[0]
    try:
        res = api.update(Table.Product, [pid], {'name': 'After Update'})
        assert res is True
        
        product = api.get_by_id(Table.Product, [pid], fields=['name'])[0]
        assert product['name'] == 'After Update'
    finally:
        api.delete(Table.Product, [pid])


def test_archive_unarchive_product(api):
    pid = api.create(Table.Product, [{'name': 'Archive Test'}])[0]
    try:
        # Archive
        api.archive(Table.Product, [pid])
        product = api.get_by_id(Table.Product, [pid], fields=['active'])[0]
        assert product['active'] is False

        # Unarchive
        api.unarchive(Table.Product, [pid])
        product = api.get_by_id(Table.Product, [pid], fields=['active'])[0]
        assert product['active'] is True
    finally:
        api.delete(Table.Product, [pid])

