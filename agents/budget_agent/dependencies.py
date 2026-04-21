from dataclasses import dataclass

from odoo.api import OdooAPIWrapper
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME


# dependencias externas que necesita el agente
@dataclass
class BudgetDependencies:
    odoo_wrapper: OdooAPIWrapper
