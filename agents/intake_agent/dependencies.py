from dataclasses import dataclass
from typing import Any

from odoo.api_wrapper import OdooAPIWrapper
from shared.config import MODEL_INTAKE_AGENT, ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME
from shared.llm import get_llm


@dataclass
class IntakeDependencies:
    llm: Any
    odoo_service: OdooAPIWrapper


def build_dependencies(model: str | None = None) -> IntakeDependencies:
    """Construye dependencias para el agente de intake."""
    return IntakeDependencies(
        llm=get_llm(model=model or MODEL_INTAKE_AGENT),
        odoo_service=OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB),
    )
