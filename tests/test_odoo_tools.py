from unittest.mock import MagicMock

from odoo.service import OdooService
from odoo.tools import build_odoo_tools


def _make_tools():
    mock_service = MagicMock(spec=OdooService)
    tools = build_odoo_tools(mock_service)
    return {t.name: t for t in tools}, mock_service


def test_build_odoo_tools_returns_nine_tools():
    tool_map, _ = _make_tools()
    assert len(tool_map) == 9


def test_buscar_productos_llama_a_search_products():
    tool_map, mock_service = _make_tools()
    mock_service.search_products.return_value = [{"id": 1, "name": "CRM Base"}]
    result = tool_map["buscar_productos"].invoke({"texto": "CRM"})
    assert result == [{"id": 1, "name": "CRM Base"}]
    mock_service.search_products.assert_called_once_with("CRM")


def test_obtener_producto_devuelve_dict_vacio_si_no_existe():
    tool_map, mock_service = _make_tools()
    mock_service.get_product_by_code.return_value = None
    result = tool_map["obtener_producto"].invoke({"codigo": "INEXISTENTE"})
    assert result == {}


def test_listar_catalogo_llama_a_list_catalog():
    tool_map, mock_service = _make_tools()
    mock_service.list_catalog.return_value = [{"id": 1, "name": "P1"}]
    result = tool_map["listar_catalogo"].invoke({})
    assert len(result) == 1
    mock_service.list_catalog.assert_called_once()


def test_buscar_cliente_devuelve_dict_vacio_si_no_existe():
    tool_map, mock_service = _make_tools()
    mock_service.find_client.return_value = None
    result = tool_map["buscar_cliente"].invoke({"nombre": "ACME"})
    assert result == {}


def test_historial_cliente_devuelve_not_found_si_no_hay_cliente():
    tool_map, mock_service = _make_tools()
    mock_service.find_client.return_value = None
    result = tool_map["historial_cliente"].invoke({"nombre": "Desconocido"})
    assert result == {"orders": [], "tickets": [], "found": False}
    mock_service.get_client_history.assert_not_called()


def test_historial_cliente_devuelve_historial_si_cliente_existe():
    tool_map, mock_service = _make_tools()
    mock_service.find_client.return_value = {"id": 42, "name": "ACME"}
    mock_service.get_client_history.return_value = {"orders": [{"id": 1}], "tickets": []}
    result = tool_map["historial_cliente"].invoke({"nombre": "ACME"})
    assert result["found"] is True
    assert len(result["orders"]) == 1
    mock_service.get_client_history.assert_called_once_with(42)


def test_listar_ordenes_cliente_devuelve_lista_vacia_si_no_hay_cliente():
    tool_map, mock_service = _make_tools()
    mock_service.find_client.return_value = None
    result = tool_map["listar_ordenes_cliente"].invoke({"nombre": "Nadie"})
    assert result == []
    mock_service.list_client_orders.assert_not_called()


def test_listar_tickets_cliente_devuelve_lista_vacia_si_no_hay_cliente():
    tool_map, mock_service = _make_tools()
    mock_service.find_client.return_value = None
    result = tool_map["listar_tickets_cliente"].invoke({"nombre": "Nadie"})
    assert result == []
    mock_service.list_client_tickets.assert_not_called()


def test_consultar_orden_devuelve_not_found_si_no_existe():
    tool_map, mock_service = _make_tools()
    mock_service.get_order.return_value = {}
    result = tool_map["consultar_orden"].invoke({"order_id": 99999})
    assert result == {"found": False}
    mock_service.get_order.assert_called_once_with(99999)


def test_consultar_ticket_devuelve_not_found_si_no_existe():
    tool_map, mock_service = _make_tools()
    mock_service.get_ticket.return_value = {}
    result = tool_map["consultar_ticket"].invoke({"ticket_id": 99999})
    assert result == {"found": False}
    mock_service.get_ticket.assert_called_once_with(99999)
