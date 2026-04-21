from dataclasses import dataclass
from typing import Any

from odoo.api import OdooAPIWrapper
from shared.config import (
    ODOO_BASE_URL,
    ODOO_DB,
    ODOO_USERNAME,
    ODOO_PASSWORD,
)
from shared.llm import get_llm


@dataclass
class TicketAgentDependencies:
    llm: Any
    odoo_service: OdooAPIWrapper


def build_ticket_dependencies() -> TicketAgentDependencies:
    return TicketAgentDependencies(
        llm=get_llm(),
        odoo_service=OdooAPIWrapper(
            url=ODOO_BASE_URL,
            username=ODOO_USERNAME,
            password=ODOO_PASSWORD,
            db=ODOO_DB,
        ),
    )