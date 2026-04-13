from odoo_integration.odoo_api_wrapper import OdooAPIWrapper
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD

wrapper = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)

def test_create_product():
    pid = wrapper.create_product({'name': 'Simple Product', 'type': 'service'})
    assert isinstance(pid, int)
    wrapper.delete_product(pid)

def test_read_product():
    pid = wrapper.create_product({'name': 'Read Me', 'type': 'service'})
    p = wrapper.get_product(pid)
    assert p['name'] == 'Read Me'
    wrapper.delete_product(pid)

def test_update_product():
    pid = wrapper.create_product({'name': 'Update Me', 'type': 'service'})
    wrapper.update_product(pid, {'list_price': 100.0})
    p = wrapper.get_product(pid)
    assert p['list_price'] == 100.0
    wrapper.delete_product(pid)

def test_list_products():
    pid = wrapper.create_product({'name': 'List Me', 'type': 'service'})
    products = wrapper.get_products(limit=100)
    assert any(p['id'] == pid for p in products)
    wrapper.delete_product(pid)

def test_delete_product():
    pid = wrapper.create_product({'name': 'Delete Me', 'type': 'service'})
    res = wrapper.delete_product(pid)
    assert res is True
    assert wrapper.get_product(pid) is None

def test_create_contact():
    cid = wrapper.create_contact({'name': 'Simple Contact'})
    assert isinstance(cid, int)
    wrapper.delete_contact(cid)

def test_read_contact():
    cid = wrapper.create_contact({'name': 'Read Contact'})
    c = wrapper.get_contact(cid)
    assert c['name'] == 'Read Contact'
    wrapper.delete_contact(cid)

def test_update_contact():
    cid = wrapper.create_contact({'name': 'Update Contact'})
    wrapper.update_contact(cid, {'email': 'test@simple.com'})
    c = wrapper.get_contact(cid)
    assert c['email'] == 'test@simple.com'
    wrapper.delete_contact(cid)

def test_list_contacts():
    cid = wrapper.create_contact({'name': 'List Contact'})
    contacts = wrapper.get_contacts(limit=100)
    assert any(c['id'] == cid for c in contacts)
    wrapper.delete_contact(cid)


def test_delete_contact():
    cid = wrapper.create_contact({'name': 'Delete Contact'})
    res = wrapper.delete_contact(cid)
    assert res is True
    assert wrapper.get_contact(cid) is None

# --- SEARCH TESTS ---

def test_search():
    pid = wrapper.create_product({'name': 'Search Test', 'default_code': 'search_code'})
    ids = wrapper.search('product.product', [('default_code', '=', 'search_code')])
    assert pid in ids
    wrapper.delete_product(pid)

def test_search_read():
    pid = wrapper.create_product({'name': 'Search Read Test', 'default_code': 'read_code'})
    results = wrapper.search_read('product.product', [('default_code', '=', 'read_code')], fields=['name'])
    assert len(results) > 0
    assert results[0]['name'] == 'Search Read Test'
    wrapper.delete_product(pid)
