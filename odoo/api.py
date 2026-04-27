import xmlrpc.client
from xmlrpc.client import Fault
from odoo.helpers import Table
from sys import stderr
from typing import Any


class OdooAPIWrapper:
    def __init__(self, url, username, password, db):
        self._url = url 
        self._username = username
        self._password = password
        self._db = db
        self._uid = self._login()
        self._models = xmlrpc.client.ServerProxy(f'{self._url}/object')

    def _login(self):
        common = xmlrpc.client.ServerProxy(f'{self._url}/common')
        uid = common.authenticate(self._db, self._username, self._password, {})
        if not uid: raise RuntimeError('URL was correct, but credentials were wrong, don\'t give up ur close!')
        return uid

    # https://www.odoo.com/documentation/18.0/developer/reference/external_api.html#read-records
    def _query(self, model, method, args = None, kwargs = None):
        args = args or []
        kwargs = kwargs or {}
        return self._models.execute_kw(self._db, self._uid, self._password, str(model), method, args, kwargs)

    def get_dbs(self):
        try:
            client = xmlrpc.client.ServerProxy(f'{self._url}/db')
            return client.list()
        except Exception as e:
            print("Could not list DBs:", e)

    def install(self, module: str): 
        ids = self._query('ir.module.module', 'search', [[('name', '=', str(module))]])
        res = self._query('ir.module.module', 'button_immediate_install', [ids])
        return res if res else None

    def get_all(self, table: Table, fields: list[str] = [], limit=1000) -> list[dict] | None:
        results = self._query(table, 'search_read', [], { 'fields': fields, 'limit': limit })
        return results if results else None

    def get_by_id(self, table: Table, ids: list[int], fields: list[str] = []) -> list[dict] | None:
        results = self._query(table, 'read', [ids], { 'fields': fields })
        return results if results else None

    def get_by_value(self, table: Table, criteria: dict[str, Any], fields: list[str] = [], limit=1000) -> list[dict] | None:
        domain = [ (field, '=', value) for field,value in criteria.items() ]
        results = self._query(table, 'search_read', [domain], { 'fields': fields, 'limit': limit })
        return results if results else None

    def update(self, table: Table, ids: list[int], new_data: dict):
        res = self._query(table, 'write', [ids, new_data])
        return res if res else None

    def create(self, table: Table, rows: list[dict]):
        ids = self._query(table, 'create', [rows])
        return ids if ids else None

    def delete(self, table: Table, ids: list[int]):
        try: return self._query(table, 'unlink', [ids])
        except Fault as f: print(f.faultString, file=stderr)
        return False

    def archive(self, table: Table, ids: list[int]) -> bool:
        try: return self._query(table, 'write', [ids, {'active': False}]) # unactive rows aren't shown in the UI
        except Fault as f: print(f.faultString, file=stderr)
        return False

    def unarchive(self, table: Table, ids: list[int]) -> bool:
        try: return self._query(table, 'write', [ids, {'active': True}]) 
        except Fault as f: print(f.faultString, file=stderr)
        return False
    
    def set_param(self, key: str, value: str):
        return self._query(
            "ir.config_parameter",
            "set_param",
            [key, value]
        )

    def get_param(self, key: str):
        return self._query(
            "ir.config_parameter",
            "get_param",
            [key]
        )
