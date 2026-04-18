from odoo.api_wrapper import OdooAPIWrapper 
from odoo.helpers import Module, Table, contact_attrs
from dotenv import load_dotenv
from os import getenv
from pprint import pprint
get_attrs = lambda obj: list(obj.keys()) if isinstance(obj, dict) else list(vars(obj).keys())

load_dotenv()

odoo = OdooAPIWrapper(getenv('ODOO_BASE_URL'), getenv('ODOO_USERNAME'), getenv('ODOO_PASSWORD'), getenv('ODOO_DB'))

odoo.install_module(Module.Base)
odoo.install_module(Module.HelpdeskManagement)
odoo.install_module(Module.HelpdeskType)
odoo.install_module(Module.HelpdeskMotive)

all_contacts = odoo.get_all(Table.Contact)
print(f'get all contacts, n contacts: {len(all_contacts)}')

c1 = { 'name': 'Bob Johnson', 'email': 'bob@mail.com', 'phone': '+34 123456789', 'mobile': True, 'is_company': True, 'street': '77 Santa Barbara Rd' }
c2 = { 'name': 'Jon bob', 'email': 'john@mail.com', 'phone': '+34 987654321', 'mobile': True, 'is_company': True, 'street': '77 Santa Jemima Rd' }
ids = odoo.create(Table.Contact, [c1, c2] )
print(f'new contact/s id: {type(ids)}, value: {ids}')

c: list[dict] = odoo.get_by_id(Table.Contact, ids, contact_attrs)
print(f'get new contact by id: {type(c)}, of length: {len(c)}')
pprint(c, indent=4)

contacts: list[dict] = odoo.get_by_value(Table.Contact, {'email': 'bob@mail.com', 'mobile': True }, contact_attrs) # we pass contact attrs just to get less info back
print(f'get new contact by value: {type(contacts)}, length: {len(contacts)}')

update_success = odoo.update(Table.Contact, [ids[0]], {'phone': '+1 999 888 777', 'street': 'Updated Blvd'})
print(f'Update success: {update_success}')

contacts_ids = list(map(lambda c: c['id'], contacts))

del_res = odoo.delete(Table.Contact, contacts_ids)
print(f'delete new contact / contacts: {del_res}')

print(f"archive a contact: {odoo.archive(Table.Contact, [all_contacts[0]['id']])}")
print(f"unarchive a contact: {odoo.unarchive(Table.Contact, [all_contacts[0]['id']])}")
