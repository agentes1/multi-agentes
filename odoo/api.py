import time
import xmlrpc.client
from xmlrpc.client import Fault
from sys import stderr
from typing import Any
from enum import StrEnum


class Table(StrEnum):
    Product = 'product.product'
    Contact = 'res.partner'
    User = 'res.users'
    Ticket = 'helpdesk.ticket'
    TicketType = 'helpdesk.ticket.type'
    TicketTeam = 'helpdesk.ticket.team'
    TicketCategory = 'helpdesk.ticket.category'
    TicketStage = 'helpdesk.ticket.stage'
    TicketTag = 'helpdesk.ticket.tag'
    Order = 'sale.order'
    OrderLine = 'sale.order.line'
    SystemParameter = 'ir.config_parameter'


class OdooAPI:
    def __init__(self, url, username, password, db):
        self._url = url
        self._username = username
        self._password = password
        self._db = db
        self._uid: int | None = None
        self._models: xmlrpc.client.ServerProxy | None = None

    def _ensure_connected(self, retries: int = 10, delay: float = 6.0) -> None:
        if self._uid is not None:
            return
        last_exc: Exception = RuntimeError("Odoo not reachable")
        for attempt in range(1, retries + 1):
            try:
                self._uid = self._login()
                self._models = xmlrpc.client.ServerProxy(f'{self._url}/object')
                return
            except Exception as exc:
                last_exc = exc
                print(f"[OdooAPI] Odoo not ready (attempt {attempt}/{retries}): {exc}", file=stderr)
                if attempt < retries:
                    time.sleep(delay)
        raise RuntimeError(f"Could not connect to Odoo after {retries} attempts") from last_exc

    def _login(self) -> int:
        common = xmlrpc.client.ServerProxy(f'{self._url}/common')
        uid = common.authenticate(self._db, self._username, self._password, {})
        if not uid:
            raise RuntimeError("URL was correct, but credentials were wrong, don't give up ur close!")
        return uid

    # https://www.odoo.com/documentation/18.0/developer/reference/external_api.html#read-records
    def _query(self, model, method, args=None, kwargs=None):
        self._ensure_connected()
        args = args or []
        kwargs = kwargs or {}
        return self._models.execute_kw(self._db, self._uid, self._password, str(model), method, args, kwargs)

    def get_dbs(self):
        try:
            client = xmlrpc.client.ServerProxy(f'{self._url}/db')
            return client.list()
        except Exception as e:
            print("Could not list DBs:", e)

    def install(self, module: str) -> bool: 
        ids = self._query('ir.module.module', 'search', [[('name', '=', str(module))]])
        res = self._query('ir.module.module', 'button_immediate_install', [ids])
        return True if res else False
    
    def update_module_list(self):
        return self._query('ir.module.module', 'update_list', [])

    def get_all(self, table: Table, fields: list[str] = [], limit=1000) -> list[dict] | None:
        results = self._query(table, 'search_read', [], { 'fields': fields, 'limit': limit })
        return results if results else None

    def get_by_id(self, table: Table, ids: list[int], fields: list[str] = []) -> list[dict] | None:
        results = self._query(table, 'read', [ids], { 'fields': fields })
        return results if results else None


    def get_by_value(self, 
            table: Table, 
            criteria: dict[str, Any], 
            fields: list[str] = [], 
            exact: bool = False, 
            OR: bool = False, 
            limit=1000
        ) -> list[dict] | None:

        if exact: domain = [(f, '=', v) for f,v in criteria.items()]
        else: domain = [(f, 'ilike', v) for f,v in criteria.items()]

        if OR and len(domain) > 1:
            for _ in range(len(domain) - 1):
                domain.insert(0, '|')

        results = self._query(table, 'search_read', [domain], { 'fields': fields, 'limit': limit })
        return results if results else None


    def update(self, table: Table, ids: list[int], new_data: dict):
        res = self._query(table, 'write', [ids, new_data])
        return res if res else None

    def create(self, table: Table, rows: list[dict]) -> list[int] | None:
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
