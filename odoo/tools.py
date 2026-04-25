from langchain_core.tools import BaseTool, tool

from odoo.service import OdooService


def build_odoo_tools(service: OdooService) -> list[BaseTool]:
    """Fábrica de tools de solo lectura para que el LLM consulte Odoo sin mutar datos."""

    @tool
    def buscar_productos(texto: str) -> list:
        """Busca productos por nombre o descripción y devuelve una lista de dicts."""
        return service.search_products(texto)

    @tool
    def obtener_producto(codigo: str) -> dict:
        """Obtiene un producto por código interno. Devuelve {} si no existe."""
        return service.get_product_by_code(codigo) or {}

    @tool
    def listar_catalogo() -> list:
        """Devuelve el catálogo de productos disponible en Odoo."""
        return service.list_catalog()

    @tool
    def buscar_cliente(nombre: str) -> dict:
        """Busca un cliente por nombre. Devuelve {} si no encuentra coincidencias."""
        return service.find_client(nombre) or {}

    @tool
    def historial_cliente(nombre: str) -> dict:
        """Devuelve órdenes y tickets de un cliente. found=false si no existe."""
        client = service.find_client(nombre)
        if not client:
            return {"orders": [], "tickets": [], "found": False}
        history = service.get_client_history(client["id"])
        return {**history, "found": True}

    @tool
    def consultar_orden(order_id: int) -> dict:
        """Obtiene una orden de venta. Devuelve found=false si no existe."""
        result = service.get_order(order_id)
        return result if result else {"found": False}

    @tool
    def listar_ordenes_cliente(nombre: str) -> list:
        """Devuelve las últimas órdenes de venta del cliente indicado."""
        client = service.find_client(nombre)
        if not client:
            return []
        return service.list_client_orders(client["id"])

    @tool
    def consultar_ticket(ticket_id: int) -> dict:
        """Obtiene un ticket de soporte. Devuelve found=false si no existe."""
        result = service.get_ticket(ticket_id)
        return result if result else {"found": False}

    @tool
    def listar_tickets_cliente(nombre: str) -> list:
        """Devuelve los últimos tickets del cliente indicado."""
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
