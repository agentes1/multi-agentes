# En este archivo montamos un servidor MCP muy simple
# La idea es exponer el catálogo de precios como una herramienta estándar.
# el conocimiento de precios deja de estar embebido en el agente
# y pasa a estar publicado como capacidad externa reutilizable.

from mcp.server.fastmcp import FastMCP

# Creamos el servidor MCP. El nombre es el identificador visible del servidor.
mcp = FastMCP("pricing-server", json_response=True)

# Este pequeño catálogo, más tarde se sustituye con datos odoo
PRICING = {
    "consultoria": {"base_price": 120, "description": "Sesión de análisis inicial"},
    "automatizacion_simple": {"base_price": 450, "description": "Automatización básica de tareas"},
    "clasificacion_emails": {
        "base_price": 300,
        "description": "Clasificación automática de emails",
    },
    "respuestas_ia": {"base_price": 350, "description": "Generación de respuestas iniciales"},
    "integracion_api": {"base_price": 500, "description": "Integración básica con API externa"},
}


@mcp.tool()
def get_service_price(service_name: str) -> dict:
    """
    Devuelve el precio base y la descripción de un servicio.
    Se publica como tool MCP para que cualquier cliente compatible pueda consultarlo.
    """
    item = PRICING.get(service_name)
    if not item:
        return {
            "found": False,
            "service_name": service_name,
            "message": "Servicio no encontrado en el catálogo",
        }

    return {
        "found": True,
        "service_name": service_name,
        "base_price": item["base_price"],
        "description": item["description"],
    }


@mcp.resource("pricing://catalog")
def pricing_catalog() -> dict:
    """
    También exponemos el catálogo completo como recurso MCP.
    Un recurso en MCP encaja bien cuando quieres cargar contexto legible
    en vez de ejecutar una acción tipo herramienta.
    """
    return PRICING


if __name__ == "__main__":
    # Lo levantamos con transporte HTTP streamable.
    mcp.run(transport="streamable-http")
