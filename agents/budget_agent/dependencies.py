from dataclasses import dataclass

from odoo.api_wrapper import OdooAPIWrapper
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME


# dependencias externas que necesita el agente
@dataclass
class BudgetDependencies:
    odoo_wrapper: OdooAPIWrapper


def build_dependencies(model: str | None = None) -> BudgetDependencies:
    return BudgetDependencies(
        odoo_wrapper=OdooAPIWrapper(
            url=ODOO_BASE_URL,
            username=ODOO_USERNAME,
            password=ODOO_PASSWORD,
            db=ODOO_DB,
        )
    )
