from __future__ import annotations

from odoo import odoo_mcp_server


class OdooMCPClient:
    """Cliente local para acceder a las tools MCP de Odoo.

    Los agentes dependen de este cliente, no del servidor directamente.
    Así podemos cambiar a un MCP remoto sin tocar la lógica de los agentes.
    """

    # Catálogo y productos
    def list_catalog(self) -> dict:
        """Devuelve el catálogo completo de productos."""
        return odoo_mcp_server.list_catalog()

    def find_products_by_text(self, text: str, limit: int = 5) -> list[dict]:
        """Busca productos por texto libre."""
        return odoo_mcp_server.find_products_by_text(text=text, limit=limit)

    def get_product(self, product_id: int) -> dict | None:
        """Obtiene un producto concreto."""
        return odoo_mcp_server.get_product(product_id=product_id)

    def get_product_catalog_snapshot(self, product_ids: list[int]) -> list[dict]:
        """Obtiene detalles resumidos de varios productos."""
        return odoo_mcp_server.get_product_catalog_snapshot(product_ids=product_ids)

    def find_related_products(self, product_ids: list[int], limit: int = 3) -> list[dict]:
        """Busca productos relacionados con una selección previa."""
        return odoo_mcp_server.find_related_products(product_ids=product_ids, limit=limit)

    # Clientes
    def find_company(self, name: str, exact: bool = False, limit: int = 5) -> list[dict]:
        """Busca empresas existentes en Odoo."""
        return odoo_mcp_server.find_company(name=name, exact=exact, limit=limit)

    def get_or_create_contact(self, company_name: str, email: str | None = None) -> int:
        """Busca o crea un contacto comercial."""
        return odoo_mcp_server.get_or_create_contact(company_name=company_name, email=email)

    def get_customer_profile(self, company_name: str) -> dict:
        """Obtiene un resumen comercial del cliente."""
        return odoo_mcp_server.get_customer_profile(company_name=company_name)

    def get_customer_history(self, partner_id: int, limit: int = 10) -> dict:
        """Obtiene historial reciente de pedidos y tickets."""
        return odoo_mcp_server.get_customer_history(partner_id=partner_id, limit=limit)

    # CRM / Ventas
    def find_crm_opportunity_by_source_ticket(self, ticket_id: int) -> dict | None:
        """Busca una oportunidad creada desde un ticket concreto."""
        return odoo_mcp_server.find_crm_opportunity_by_source_ticket(ticket_id=ticket_id)

    def create_crm_opportunity(
        self,
        title: str,
        description: str,
        partner_id: int | None = None,
        partner_name: str | None = None,
        partner_email: str | None = None,
        source_ticket_id: int | None = None,
        priority: str | None = None,
    ) -> int:
        """Crea una oportunidad comercial en CRM."""
        return odoo_mcp_server.create_crm_opportunity(
            title=title,
            description=description,
            partner_id=partner_id,
            partner_name=partner_name,
            partner_email=partner_email,
            source_ticket_id=source_ticket_id,
            priority=priority,
        )

    def get_crm_opportunity(self, opportunity_id: int) -> dict | None:
        """Lee una oportunidad comercial por ID."""
        return odoo_mcp_server.get_crm_opportunity(opportunity_id=opportunity_id)

    # Presupuestos
    def find_sale_order_by_client_ref(self, client_order_ref: str) -> dict | None:
        """Busca un presupuesto por referencia externa."""
        return odoo_mcp_server.find_sale_order_by_client_ref(client_order_ref=client_order_ref)

    def create_sale_order(self, partner_id: int, client_order_ref: str | None = None) -> int:
        """Crea la cabecera de un presupuesto."""
        return odoo_mcp_server.create_sale_order(partner_id=partner_id, client_order_ref=client_order_ref)

    def create_sale_order_line(self, order_id: int, product_id: int, quantity: int = 1) -> int:
        """Añade una línea de producto al presupuesto."""
        return odoo_mcp_server.create_sale_order_line(order_id=order_id, product_id=product_id, quantity=quantity)

    def get_sale_order(self, order_id: int) -> dict | None:
        """Lee un presupuesto desde Odoo."""
        return odoo_mcp_server.get_sale_order(order_id=order_id)

    def get_sale_order_lines(self, order_id: int) -> list[dict]:
        """Lee las líneas de un presupuesto."""
        return odoo_mcp_server.get_sale_order_lines(order_id=order_id)

    # Helpdesk
    def find_helpdesk_team(self, name: str) -> dict | None:
        """Busca un equipo de Helpdesk por nombre."""
        return odoo_mcp_server.find_helpdesk_team(name=name)

    def find_ticket_type(self, name: str) -> dict | None:
        """Busca un tipo de ticket."""
        return odoo_mcp_server.find_ticket_type(name=name)

    def find_ticket_category(self, name: str) -> dict | None:
        """Busca una categoría de ticket."""
        return odoo_mcp_server.find_ticket_category(name=name)

    def find_ticket_tags(self, names: list[str]) -> list[int]:
        """Busca etiquetas de Helpdesk y devuelve sus IDs."""
        return odoo_mcp_server.find_ticket_tags(names=names)

    def create_helpdesk_ticket(
        self, title: str, description: str, team_id: int, priority: str = "1",
        type_id: int | None = None, category_id: int | None = None,
        tag_ids: list[int] | None = None, partner_id: int | None = None,
        partner_name: str | None = None, partner_email: str | None = None,
        origin_channel: str = "email",
    ) -> int:
        """Crea un ticket de Helpdesk en Odoo."""
        return odoo_mcp_server.create_helpdesk_ticket(
            title=title, description=description, team_id=team_id, priority=priority,
            type_id=type_id, category_id=category_id, tag_ids=tag_ids,
            partner_id=partner_id, partner_name=partner_name,
            partner_email=partner_email, origin_channel=origin_channel,
        )

    def post_message_to_ticket(self, ticket_id: int, body: str) -> bool:
        """Publica un mensaje en el chatter de un ticket."""
        return odoo_mcp_server.post_message_to_ticket(ticket_id=ticket_id, body=body)
