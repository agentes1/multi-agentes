from dataclasses import dataclass
from typing import Any

from odoo.api import OdooAPIWrapper
from odoo.service import OdooService
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME
from shared.llm import get_llm

from .schemas import Budget


@dataclass
class BudgetDependencies:
    llm: Any
    structured_llm: Any
    odoo_service: OdooService


def build_budget_dependencies() -> BudgetDependencies:
    llm = get_llm()
    wrapper = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)

    return BudgetDependencies(
        llm=llm,
        structured_llm=llm.with_structured_output(Budget),
        odoo_service=OdooService(wrapper),
    )