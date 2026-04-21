from dataclasses import dataclass
from typing import Any

from shared.llm import get_llm
from shared.config import (
    ODOO_BASE_URL,
    ODOO_DB,
    ODOO_USERNAME,
    ODOO_PASSWORD,
)

from odoo.api import OdooAPIWrapper


@dataclass
class TicketAgentDependencies:
    llm: Any
    odoo_service: OdooAPIWrapper


def build_ticket_dependencies() -> TicketAgentDependencies:
    """
    Construye todas las dependencias reales del agente.
    """

    return TicketAgentDependencies(
        llm=get_llm(),
        odoo_service=OdooAPIWrapper(
            url=ODOO_BASE_URL,
            username=ODOO_USERNAME,
            password=ODOO_PASSWORD,
            db=ODOO_DB,
        ),
    )