from unittest.mock import MagicMock

from odoo.helpers import Table
from odoo.resolvers import (
    find_record_id,
    find_record_ids,
    get_ticket_field_names,
    resolve_company,
)
from odoo.service import OdooService


def test_resolve_company_devuelve_match_y_debug():
    mock_service = MagicMock(spec=OdooService)
    mock_service.find_company.side_effect = [[{"id": 1, "name": "ACME"}]]
    company, debug = resolve_company(mock_service, "ACME", "ana@acme.com")
    assert company == {"id": 1, "name": "ACME"}
    assert debug["candidates"] == ["ACME"]


def test_find_record_id_y_ids_delegan_en_service():
    mock_service = MagicMock(spec=OdooService)
    mock_service.find_record_id_by_name.side_effect = [10, 20]
    assert find_record_id(mock_service, Table.TicketTeam, "Soporte") == 10
    assert find_record_ids(mock_service, Table.TicketTag, ["Urgente", "Urgente", "VIP"]) == [20]


def test_get_ticket_field_names_delega_en_service():
    mock_service = MagicMock(spec=OdooService)
    mock_service.get_model_fields.return_value = {"name", "description"}
    assert get_ticket_field_names(mock_service) == {"name", "description"}
