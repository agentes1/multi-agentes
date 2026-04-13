# agents/intake_agent/dependencies.py
from dataclasses import dataclass

from odoo_integration.odoo_api_wrapper import OdooAPIWrapper
from shared.config import ODOO_DB, ODOO_PASSWORD, ODOO_BASE_URL, ODOO_USERNAME
from shared.llm import get_llm


@dataclass
class IntakeDependencies:
    llm: object
    odoo_service: OdooAPIWrapper


def build_dependencies(model: str | None = None) -> IntakeDependencies:
    return IntakeDependencies(
        llm=get_llm(model=model),
        odoo_service=OdooAPIWrapper(
            url=ODOO_BASE_URL,
            username=ODOO_USERNAME,
            password=ODOO_PASSWORD,
            db=ODOO_DB,
        ),
    )