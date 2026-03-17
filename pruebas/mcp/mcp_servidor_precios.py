from typing import Any

from mcp.server.fastmcp import FastMCP

# Creo un servidor MCP muy simple que simula los datos que mañana saldrán de Odoo.
# La idea es mantener una interfaz estable para que el agente no cambie cuando
# sustituyamos esta simulación por la API real.
mcp = FastMCP("odoo_precios_simulados")

CATALOGO = {
    "crm_base": {
        "name": "CRM Base",
        "price": 1200,
        "description": "Gestión básica de leads, oportunidades y pipeline comercial",
    },
    "email_ai": {
        "name": "Clasificación de emails con IA",
        "price": 1800,
        "description": "Clasificación automática de correos y sugerencia de respuesta",
    },
    "quotation_ai": {
        "name": "Generación de presupuestos con IA",
        "price": 2200,
        "description": "Creación asistida de presupuestos a partir de formularios o emails",
    },
    "odoo_connector": {
        "name": "Conector con Odoo",
        "price": 1500,
        "description": "Integración con Odoo para clientes, oportunidades y presupuestos",
    },
    "dashboard": {
        "name": "Dashboard comercial",
        "price": 900,
        "description": "Panel de seguimiento de actividad comercial y embudo",
    },
}

CLIENTES = {
    "ACME": {
        "segment": "pyme",
        "discount_pct": 10,
        "currency": "EUR",
    },
    "MEGACORP": {
        "segment": "enterprise",
        "discount_pct": 15,
        "currency": "EUR",
    },
}


@mcp.tool()
def list_catalog() -> dict[str, Any]:
    """Devuelve el catálogo completo de módulos presupuestables."""
    return CATALOGO


@mcp.tool()
def get_product(product_code: str) -> dict[str, Any]:
    """Devuelve el detalle de un producto a partir de su código."""
    if product_code not in CATALOGO:
        raise ValueError(f"Producto no encontrado: {product_code}")
    return CATALOGO[product_code]


@mcp.tool()
def get_customer_profile(company_name: str) -> dict[str, Any]:
    """Devuelve información comercial básica del cliente."""
    return CLIENTES.get(
        company_name.upper(),
        {"segment": "desconocido", "discount_pct": 0, "currency": "EUR"},
    )


@mcp.tool()
def calculate_quote(product_codes: list[str], company_name: str) -> dict[str, Any]:
    """Calcula subtotal, descuento y total final para la lista de módulos."""
    customer = CLIENTES.get(
        company_name.upper(),
        {"segment": "desconocido", "discount_pct": 0, "currency": "EUR"},
    )

    lines = []
    subtotal = 0

    for code in product_codes:
        if code not in CATALOGO:
            continue

        product = CATALOGO[code]
        lines.append(
            {
                "code": code,
                "name": product["name"],
                "unit_price": product["price"],
            }
        )
        subtotal += product["price"]

    discount_pct = customer["discount_pct"]
    discount_amount = round(subtotal * discount_pct / 100, 2)
    total = round(subtotal - discount_amount, 2)

    return {
        "company_name": company_name,
        "currency": customer["currency"],
        "segment": customer["segment"],
        "discount_pct": discount_pct,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "total": total,
        "lines": lines,
    }


if __name__ == "__main__":
    # Lo ejecuto por stdio porque el cliente MCP del agente se conectará así.
    # Aquí no hago prints porque en un servidor MCP por stdio no debemos escribir
    # a stdout; si no, se rompe la comunicación con el cliente.
    mcp.run()
