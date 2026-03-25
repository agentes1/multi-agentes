REQUIREMENT_TO_PRODUCT = {
    "crm": "crm_base",
    "emails": "email_ai",
    "presupuestos": "quotation_ai",
    "odoo": "odoo_connector",
    "dashboard": "dashboard",
}


REQUIREMENT_SYNONYMS = {
    "correo": "emails",
    "email": "emails",
    "mails": "emails",
    "mail": "emails",
    "automatizacion comercial": "crm",
    "comercial": "crm",
    "erp": "odoo",
    "informes": "dashboard",
    "reporting": "dashboard",
    "cotizaciones": "presupuestos",
}


def normalize_requirement(requirement: str) -> str:
    value = str(requirement).lower().strip()
    return REQUIREMENT_SYNONYMS.get(value, value)


def map_requirements_to_products(requirements: list[str]) -> list[str]:
    products: list[str] = []

    for req in requirements:
        normalized = normalize_requirement(req)
        code = REQUIREMENT_TO_PRODUCT.get(normalized)

        if code and code not in products:
            products.append(code)

    return products
