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


class OdooAPI:
    """Cliente mínimo para trabajar con Odoo mediante XML-RPC."""

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        db: str,
        login_retries: int = 12,
        login_retry_delay: float = 2.0,
    ):
        self._url = self._normalize_url(url)
        self._username, self._password, self._db = username, password, db
        self._login_retries = login_retries
        self._login_retry_delay = login_retry_delay
        self._uid = self._login()
        self._models = xmlrpc.client.ServerProxy(f"{self._url}/xmlrpc/2/object")

    def _normalize_url(self, url: str) -> str:
        """Normaliza la URL base de Odoo."""
        return (url or "").rstrip("/").removesuffix("/xmlrpc/2")

    def _login(self) -> int:
        """Autentica el usuario y devuelve su UID."""
        common = xmlrpc.client.ServerProxy(f"{self._url}/xmlrpc/2/common")
        last_error: Exception | None = None
        for attempt in range(1, self._login_retries + 1):
            try:
                uid = common.authenticate(self._db, self._username, self._password, {})
                if not uid:
                    raise RuntimeError("Credenciales incorrectas para Odoo.")
                return uid
            except RuntimeError:
                raise
            except Exception as error:
                last_error = error
                if attempt == self._login_retries:
                    break
                print(
                    f"Odoo XML-RPC login failed on attempt {attempt}/{self._login_retries}: {error}. Retrying...",
                    file=stderr,
                )
                time.sleep(self._login_retry_delay)

        raise RuntimeError(
            f"No se pudo conectar con Odoo en {self._url} tras {self._login_retries} intentos."
        ) from last_error

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
        self, table: Table, criteria: dict[str, Any], fields: list[str] | None = None,
        exact: bool = False, OR: bool = False, limit: int = 1000,
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
