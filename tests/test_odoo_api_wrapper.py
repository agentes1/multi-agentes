from odoo.api import OdooAPIWrapper
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

# Search

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

# Helpdesk 
def test_get_team_id_by_name():
    team_id = wrapper.get_team_id_by_name('Soporte cliente')
    assert isinstance(team_id, int)


def test_get_ticket_type_id_by_name():
    type_id = wrapper.get_ticket_type_id_by_name('Soporte')
    assert isinstance(type_id, int)


def test_get_category_id_by_name():
    category_id = wrapper.get_category_id_by_name('Problema')
    assert isinstance(category_id, int)


def test_get_tag_ids_by_names():
    tag_ids = wrapper.get_tag_ids_by_names(['Urgente', 'Faltan datos'])
    assert isinstance(tag_ids, list)
    assert len(tag_ids) >= 1


def test_create_helpdesk_ticket_simple():
    team_id = wrapper.get_team_id_by_name('Soporte cliente')
    assert team_id is not None

    ticket_id = wrapper.create_helpdesk_ticket(
        title='Ticket test simple',
        description='Ticket creado desde test automático',
        team_id=team_id,
        priority='1',
    )

    assert isinstance(ticket_id, int)

    # comprobamos que el ticket existe
    tickets = wrapper.search_read(
        'helpdesk.ticket',
        [('id', '=', ticket_id)],
        fields=['name', 'description', 'team_id', 'priority'],
        limit=1,
    )

    assert len(tickets) == 1
    assert tickets[0]['name'] == 'Ticket test simple'
    assert tickets[0]['priority'] == '1'

    # limpieza
    wrapper._models.execute_kw(
        wrapper._db,
        wrapper._uid,
        wrapper._password,
        'helpdesk.ticket',
        'unlink',
        [[ticket_id]],
    )


def test_create_helpdesk_ticket_full():
    team_id = wrapper.get_team_id_by_name('Presupuestos')
    type_id = wrapper.get_ticket_type_id_by_name('Presupuesto')
    category_id = wrapper.get_category_id_by_name('Consulta presupuesto')
    tag_ids = wrapper.get_tag_ids_by_names(['Cliente nuevo', 'Faltan datos'])

    assert team_id is not None
    assert type_id is not None
    assert category_id is not None

    ticket_id = wrapper.create_helpdesk_ticket(
        title='Ticket test presupuesto',
        description='Solicitud de presupuesto creada desde test',
        team_id=team_id,
        priority='2',
        type_id=type_id,
        category_id=category_id,
        tag_ids=tag_ids,
    )

    assert isinstance(ticket_id, int)

    # comprobamos campos principales del ticket creado
    tickets = wrapper.search_read(
        'helpdesk.ticket',
        [('id', '=', ticket_id)],
        fields=['name', 'team_id', 'type_id', 'category_id', 'priority', 'tag_ids'],
        limit=1,
    )

    assert len(tickets) == 1

    ticket = tickets[0]
    assert ticket['name'] == 'Ticket test presupuesto'
    assert ticket['priority'] == '2'
    assert ticket['team_id'][0] == team_id
    assert ticket['type_id'][0] == type_id
    assert ticket['category_id'][0] == category_id

    # limpieza
    wrapper._models.execute_kw(
        wrapper._db,
        wrapper._uid,
        wrapper._password,
        'helpdesk.ticket',
        'unlink',
        [[ticket_id]],
    )


def test_list_helpdesk_tickets():
    team_id = wrapper.get_team_id_by_name('Soporte cliente')
    ticket_id = wrapper.create_helpdesk_ticket(
        title='Ticket para listar',
        description='Ticket temporal para test de listado',
        team_id=team_id,
        priority='1',
    )

    tickets = wrapper.get_helpdesk_tickets(limit=100)
    assert any(t['id'] == ticket_id for t in tickets)

    # limpieza
    wrapper._models.execute_kw(
        wrapper._db,
        wrapper._uid,
        wrapper._password,
        'helpdesk.ticket',
        'unlink',
        [[ticket_id]],
    )
