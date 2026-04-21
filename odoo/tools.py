from langchain_core.tools import BaseTool, tool

from odoo.service import OdooService


def build_odoo_tools(service: OdooService) -> list[BaseTool]:
    """Fábrica de LangChain tools de solo lectura sobre OdooService.

    TOOL-CALLING — solo lectura.
    El LLM decide cuándo y qué consultar según el contexto de la conversación.
    Si una tool falla, no modifica nada en Odoo.

    MUTACIONES — nodos hardcodeados del grafo (NO aquí).
    Razón: crear tickets, órdenes y contactos debe ser determinista.
    Un LLM que alucina no puede crear registros en producción de forma autónoma.
    """

    @tool
    def buscar_productos(texto: str) -> list:
        """Busca productos en el catálogo de Odoo por nombre o descripción (búsqueda parcial). Devuelve lista de dicts con claves: id, name, default_code, list_price, type. Devuelve [] si no hay coincidencias."""
        return service.search_products(texto)

    @tool
    def obtener_producto(codigo: str) -> dict:
        """Obtiene detalles completos de un producto por su código interno (default_code, ej: 'crm_base'). Devuelve dict con id, name, default_code, list_price, type. Devuelve {} si el código no existe."""
        return service.get_product_by_code(codigo) or {}

    @tool
    def listar_catalogo() -> list:
        """Devuelve todos los productos disponibles en Odoo (máx 100). Cada elemento tiene: id, name, default_code, list_price."""
        return service.list_catalog()

    @tool
    def buscar_cliente(nombre: str) -> dict:
        """Busca si existe un cliente en Odoo por nombre (búsqueda parcial). Devuelve dict con id, name, email, phone, is_company. Devuelve {} si no existe."""
        return service.find_client(nombre) or {}

    @tool
    def historial_cliente(nombre: str) -> dict:
        """Devuelve el historial completo de un cliente: órdenes de venta anteriores y tickets de soporte. Resultado: {"found": bool, "orders": [...], "tickets": [...]}. "found": false si el cliente no existe en Odoo."""
        client = service.find_client(nombre)
        if not client:
            return {"orders": [], "tickets": [], "found": False}
        history = service.get_client_history(client["id"])
        return {**history, "found": True}

    @tool
    def consultar_orden(order_id: int) -> dict:
        """Obtiene el estado, total y fecha de una orden de venta por ID. Devuelve {"found": False} si no existe."""
        result = service.get_order(order_id)
        return result if result else {"found": False}

    @tool
    def listar_ordenes_cliente(nombre: str) -> list:
        """Devuelve las últimas 10 órdenes de venta de un cliente buscando por nombre. Cada orden tiene: id, name, state, amount_total, date_order. Devuelve [] si el cliente no existe."""
        client = service.find_client(nombre)
        if not client:
            return []
        return service.list_client_orders(client["id"])

    @tool
    def consultar_ticket(ticket_id: int) -> dict:
        """Obtiene el estado y descripción de un ticket de soporte por ID. Devuelve {"found": False} si no existe."""
        result = service.get_ticket(ticket_id)
        return result if result else {"found": False}

    @tool
    def listar_tickets_cliente(nombre: str) -> list:
        """Devuelve los últimos 10 tickets de soporte de un cliente buscando por nombre. Cada ticket tiene: id, name, stage_id, team_id. Devuelve [] si el cliente no existe."""
        client = service.find_client(nombre)
        if not client:
            return []
        return service.list_client_tickets(client["id"])

    return [
        buscar_productos,
        obtener_producto,
        listar_catalogo,
        buscar_cliente,
        historial_cliente,
        consultar_orden,
        listar_ordenes_cliente,
        consultar_ticket,
        listar_tickets_cliente,
    ]
