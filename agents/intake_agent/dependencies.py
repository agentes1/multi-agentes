from dataclasses import dataclass
from typing import Any

from shared.llm import get_llm
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD
from odoo.api import OdooAPIWrapper
from odoo.service import OdooService


@dataclass
class TicketAgentDependencies:
    llm: Any
    odoo_service: OdooService


def build_ticket_dependencies() -> TicketAgentDependencies:
    wrapper = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)
    return TicketAgentDependencies(
        llm=get_llm(),
        odoo_service=OdooService(wrapper),
    )
