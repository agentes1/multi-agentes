from dataclasses import dataclass

from odoo.api import OdooAPIWrapper


# dependencias externas que necesita el agente
@dataclass
class BudgetDependencies:
    odoo_wrapper: OdooAPIWrapper