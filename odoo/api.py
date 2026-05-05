import time
import time
import xmlrpc.client
from enum import StrEnum
from sys import stderr
from typing import Any
from xmlrpc.client import Fault


class Table(StrEnum):
    Product = "product.product"
    Contact = "res.partner"
    User = "res.users"
    Lead = "crm.lead"
    Ticket = "helpdesk.ticket"
    TicketType = "helpdesk.ticket.type"
    TicketTeam = "helpdesk.ticket.team"
    TicketCategory = "helpdesk.ticket.category"
    TicketStage = "helpdesk.ticket.stage"
    TicketTag = "helpdesk.ticket.tag"
    HelpdeskTeam = "helpdesk.ticket.team"
    Order = "sale.order"
    OrderLine = "sale.order.line"
    SystemParameter = "ir.config_parameter"
    MailInboxMessage = "mail.inbox.message"


class OdooAPI:
    """Cliente mínimo para trabajar con Odoo mediante XML-RPC."""

    def __init__(self, url: str, username: str, password: str, db: str):
        self._url = url
        self._username = username
        self._password = password
        self._db = db
        self._uid = self._login()
        self._models = xmlrpc.client.ServerProxy(f'{self._url}/object')

    def _login(self):
        common = xmlrpc.client.ServerProxy(f'{self._url}/common')
        uid = common.authenticate(self._db, self._username, self._password, {})
        if not uid: raise RuntimeError('URL was correct, but credentials were wrong, don\'t give up you\'re close!')
        return uid


    def install(self, module_name: str) -> bool:
        """
        Installs an Odoo module by its technical name.
        """
        module_ids = self._query('ir.module.module', 'search', [[['name', '=', module_name]]])
        if not module_ids: return False # not found

        module_data = self._query('ir.module.module', 'read', [module_ids, ['name', 'state']])
        if module_data and module_data[0]["state"] == "installed":
            return False # already installed
    
        self._query('ir.module.module', 'button_immediate_install', [module_ids])
        return True

    def update_module_list(self):
        """
        Updates the Odoo apps/module list.
        Equivalent to clicking 'Update Apps List' in Odoo.
        """
        self._query('ir.module.module', 'update_list')
    
    def _query(self, model: Table | str, method: str, args: list | None = None, kwargs: dict | None = None) -> Any:
        """Ejecuta un método ORM de Odoo."""
        return self._models.execute_kw(self._db, self._uid, self._password, str(model), method, args or [], kwargs or {})

    def search_read(self, table: Table, domain: list, fields: list[str] | None = None, limit: int = 1000) -> list[dict] | None:
        """Busca registros y devuelve sus campos."""
        results = self._query(table, "search_read", [domain], {"fields": fields or [], "limit": limit})
        return results or None

    def get_all(self, table: Table, fields: list[str] | None = None, limit: int = 1000) -> list[dict] | None:
        """Devuelve registros de una tabla."""
        return self.search_read(table, [], fields, limit)

    def get_by_id(self, table: Table, ids: list[int], fields: list[str] | None = None) -> list[dict] | None:
        """Lee registros por ID."""
        results = self._query(table, "read", [ids], {"fields": fields or []})
        return results or None

    def get_by_value(
        self, 
        table: Table, 
        criteria: dict[str, Any], 
        fields: list[str] | None = None,
        exact: bool = False, 
        OR: bool = False, 
        limit: int = 1000,
    ) -> list[dict] | None:
        """Busca registros por uno o varios campos."""
        operator = "=" if exact else "ilike"
        domain = [(field, operator, value) for field, value in criteria.items()]
        if OR and len(domain) > 1: domain = ["|"] * (len(domain) - 1) + domain
        return self.search_read(table, domain, fields, limit)

    def create(self, table: Table, rows: list[dict], context: dict[str, Any] | None = None) -> list[int] | None:
        """Crea registros y devuelve sus IDs."""
        ids = self._query(table, "create", [rows], {"context": context} if context else None)
        return ids or None

    def update(self, table: Table, ids: list[int], values: dict) -> bool:
        """Actualiza registros."""
        return bool(self._query(table, "write", [ids, values]))

    def delete(self, table: Table, ids: list[int]) -> bool:
        """Elimina registros."""
        try: return bool(self._query(table, "unlink", [ids]))
        except Fault as fault:
            print(fault.faultString, file=stderr)
            return False

    def archive(self, table: Table, ids: list[int]) -> bool:
        """Archiva registros usando active=False."""
        try: return bool(self._query(table, "write", [ids, {"active": False}]))
        except Fault as fault:
            print(fault.faultString, file=stderr)
            return False

    class NotificationType(StrEnum):
        Info = 'info'
        Success = 'success'
        Warning = 'warning'
        Danger = 'danger'

    def notification(self, title: str, msg: str, type: NotificationType = NotificationType.Info) -> bool: 
        user_data = self.get_by_id(Table.User, [self._uid], ['partner_id'])
        if not user_data or not user_data[0].get('partner_id'):
            return False 

        target_partner_id = user_data[0]['partner_id'][0]
        # Call the PUBLIC method we created in our custom module
        self._query('bus.bus', 'send_rpc_notification', [target_partner_id, title,  msg, type.value])
        return True
