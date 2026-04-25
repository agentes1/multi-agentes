from dataclasses import dataclass, field
from typing import Any

from odoo.api import OdooAPIWrapper
from odoo.service import OdooService
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME
from shared.llm import get_llm

from .schemas import Ticket


@dataclass
class TicketAgentDependencies:
    llm: Any
    odoo_service: OdooService
    structured_llm: Any = field(default=None)


def build_ticket_dependencies() -> TicketAgentDependencies:
    llm = get_llm()
    wrapper = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)
    return TicketAgentDependencies(
        llm=llm,
        odoo_service=OdooService(wrapper),
        structured_llm=llm.with_structured_output(schema=Ticket),
    )
