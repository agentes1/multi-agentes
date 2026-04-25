import json
import re
import uuid

import pytest

from agents.intake_agent.dependencies import TicketAgentDependencies
from agents.intake_agent.graph import build_ticket_graph
from agents.intake_agent.schemas import NormalizedTicket, SenderIdentity
from odoo.helpers import Table


class MockLLMResponse:
    def __init__(self, content: str, structured: bool = False, schema_name: str | None = None):
        self._content = content
        self._structured = structured
        self._schema_name = schema_name

    def bind_tools(self, tools):
        return self

    def with_structured_output(self, schema):
        return MockLLMResponse(self._content, structured=True, schema_name=schema.__name__)

    async def ainvoke(self, messages):
        if self._structured:
            payload = json.loads(self._content)
            if self._schema_name == "SenderIdentity":
                sender_email = ""
                sender_name = ""
                for message in messages:
                    content = getattr(message, "content", "")
                    if "Remitente email:" in content:
                        for line in str(content).splitlines():
                            if line.startswith("Remitente email:"):
                                sender_email = line.split(":", 1)[1].strip()
                            if line.startswith("Remitente nombre:"):
                                sender_name = line.split(":", 1)[1].strip()
                company_name = payload.get("company_name")
                partner_name = payload.get("partner_name")
                if not company_name and sender_email:
                    domain = sender_email.split("@", 1)[-1].split(".")[0]
                    company_name = domain.upper() if len(domain) <= 4 else domain.capitalize()
                if not partner_name:
                    partner_name = None if not sender_name or sender_name == "None" else sender_name
                    if not partner_name and sender_email:
                        local = sender_email.split("@", 1)[0]
                        partner_name = " ".join(part.capitalize() for part in re.split(r"[\s._\-+]+", local) if part)
                return SenderIdentity.model_validate(
                    {"company_name": company_name, "partner_name": partner_name}
                )
            return NormalizedTicket.model_validate(payload)

        class Response:
            content = self._content
            tool_calls = []

        return Response()


class FakeOdooService:
    def __init__(self):
        self._wrapper = self
        self.next_contact_id = 2
        self.next_ticket_id = 1
        self.contacts = [
            {
                "id": 1,
                "name": "ACME",
                "email": "info@acme.com",
                "is_company": True,
                "customer_rank": 1,
            }
        ]
        self.teams = [
            {"id": 10, "name": "Presupuestos"},
            {"id": 11, "name": "Soporte cliente"},
        ]
        self.types = [
            {"id": 20, "name": "Presupuesto"},
            {"id": 21, "name": "Soporte"},
        ]
        self.categories = [
            {"id": 30, "name": "Consulta presupuesto"},
            {"id": 31, "name": "Problema"},
            {"id": 32, "name": "Interno"},
        ]
        self.stages = [
            {"id": 40, "name": "Nuevo"},
        ]
        self.tags = [
            {"id": 50, "name": "Urgente"},
            {"id": 51, "name": "Cliente nuevo"},
            {"id": 52, "name": "Faltan datos"},
            {"id": 53, "name": "Pendiente validación"},
        ]
        self.tickets = []

    def _query(self, model, method, args=None, kwargs=None):
        args = args or []
        kwargs = kwargs or {}

        if str(model) == str(Table.Ticket) and method == "fields_get":
            return {
                "name": {"type": "char"},
                "description": {"type": "text"},
                "priority": {"type": "selection"},
                "partner_id": {"type": "many2one"},
                "partner_email": {"type": "char"},
                "partner_name": {"type": "char"},
                "team_id": {"type": "many2one"},
                "type_id": {"type": "many2one"},
                "category_id": {"type": "many2one"},
                "stage_id": {"type": "many2one"},
                "tag_ids": {"type": "many2many"},
            }

        if method == "create":
            vals = args[0] if args else {}
            return self.create(model, vals)

        if method != "search_read":
            raise NotImplementedError(f"Unsupported method: {model}.{method}")

        domain = args[0] if args else []
        limit = kwargs.get("limit", 1)
        records = self._records_for_model(model)
        matched = [record for record in records if self._matches_domain(record, domain)]
        return matched[:limit]

    def get_by_value(self, table, criteria, fields=None, limit=1000):
        records = self._records_for_model(table)
        matched = []
        for record in records:
            if all(record.get(field) == value for field, value in criteria.items()):
                matched.append(record)
        return matched[:limit] or None

    def create(self, table, rows):
        if str(table) == str(Table.Contact):
            row = {"id": self.next_contact_id, **rows}
            self.next_contact_id += 1
            self.contacts.append(row)
            return row["id"]

        if str(table) == str(Table.Ticket):
            row = {"id": self.next_ticket_id, **rows}
            self.next_ticket_id += 1
            self.tickets.append(row)
            return row["id"]

        raise NotImplementedError(f"Unsupported create table: {table}")

    def _records_for_model(self, model):
        model_name = str(model)
        if model_name == str(Table.Contact):
            return self.contacts
        if model_name == str(Table.TicketTeam):
            return self.teams
        if model_name == str(Table.TicketType):
            return self.types
        if model_name == str(Table.TicketCategory):
            return self.categories
        if model_name == str(Table.TicketStage):
            return self.stages
        if model_name == str(Table.TicketTag):
            return self.tags
        raise NotImplementedError(f"Unsupported model: {model_name}")

    def _matches_domain(self, record, domain):
        for field, operator, value in domain:
            record_value = record.get(field)
            if operator == "=" and record_value != value:
                return False
            if operator == "=ilike":
                if record_value is None or str(record_value).casefold() != str(value).casefold():
                    return False
            if operator == "ilike":
                if record_value is None or str(value).casefold() not in str(record_value).casefold():
                    return False
        return True

    # Estas helpers imitan la interfaz real de OdooService usada por odoo.tools.
    def find_company(self, name: str, exact: bool = False, limit: int = 5):
        operator = "=ilike" if exact else "ilike"
        return self._query(
            Table.Contact,
            "search_read",
            [[("is_company", "=", True), ("name", operator, name)]],
            {"fields": ["id", "name", "email", "is_company"], "limit": limit},
        )

    def find_record_id_by_name(self, model: str, name: str):
        records = self._query(
            model,
            "search_read",
            [[("name", "=ilike", name)]],
            {"fields": ["id", "name"], "limit": 1},
        )
        return records[0]["id"] if records else None

    def get_model_fields(self, model: str):
        if str(model) == str(Table.Ticket):
            return set(self._query(model, "fields_get").keys())
        return set()

    def create_company_contact(self, name: str, email: str | None = None):
        vals = {"name": name, "is_company": True, "customer_rank": 1}
        if email:
            vals["email"] = email
        return self._query(Table.Contact, "create", [vals])


def _build_deps(mock_json: str, odoo_service: FakeOdooService | None = None) -> TicketAgentDependencies:
    llm = MockLLMResponse(mock_json)
    return TicketAgentDependencies(
        llm=llm,
        odoo_service=odoo_service or FakeOdooService(),
        structured_llm=llm.with_structured_output(schema=NormalizedTicket),
        sender_identity_llm=llm.with_structured_output(schema=SenderIdentity),
    )


def _base_config(deps: TicketAgentDependencies) -> dict:
    return {
        "configurable": {
            "deps": deps,
            "thread_id": f"test-intake-agent-{uuid.uuid4()}",
        }
    }


@pytest.mark.asyncio
async def test_email_cliente_antiguo_presupuesto_muy_urgente():
    graph = build_ticket_graph()
    odoo_service = FakeOdooService()
    deps = _build_deps(
        """{
            "title": "Presupuesto urgente para CRM",
            "description": "Necesitamos una propuesta urgente para implantar CRM.",
            "company_name": null,
            "partner_name": null,
            "customer_email": "ana_lopez@acme.com",
            "team": null,
            "ticket_type": "presupuesto",
            "category": null,
            "stage": null,
            "tags": [],
            "priority": "muy urgente"
        }""",
        odoo_service=odoo_service,
    )

    result = await graph.ainvoke(
        {
            "email_subject": "Presupuesto CRM",
            "email_body": "Necesito un presupuesto urgente para un CRM.",
            "sender_email": "ana_lopez@acme.com",
            "sender_name": None,
            "team_name": None,
        },
        config=_base_config(deps),
    )

    assert result.get("error") is None
    assert result["partner_id"] == 1
    assert result["company_is_new"] is False
    assert result["normalized_ticket"].company_name == "ACME"
    assert result["normalized_ticket"].partner_name == "Ana Lopez"
    assert result["resolved_fields"].team_name == "Presupuestos"
    assert "Urgente" in result["resolved_fields"].tag_names
    assert "Cliente nuevo" not in result["resolved_fields"].tag_names
    assert result["ticket_vals"]["partner_name"] == "Ana Lopez"
    assert result["ticket_vals"]["partner_email"] == "ana_lopez@acme.com"
    assert "Datos que faltan" not in result["ticket_vals"]["description"]


@pytest.mark.asyncio
async def test_email_cliente_nuevo_crea_empresa_y_tag_cliente_nuevo():
    graph = build_ticket_graph()
    odoo_service = FakeOdooService()
    deps = _build_deps(
        """{
            "title": "Incidencia en portal",
            "description": "No podemos acceder al portal de clientes.",
            "company_name": null,
            "partner_name": null,
            "customer_email": "laura@newco.com",
            "team": null,
            "ticket_type": "incidencia",
            "category": null,
            "stage": null,
            "tags": [],
            "priority": "normal"
        }""",
        odoo_service=odoo_service,
    )

    result = await graph.ainvoke(
        {
            "email_subject": "Error de acceso",
            "email_body": "No podemos acceder al portal.",
            "sender_email": "laura@newco.com",
            "sender_name": None,
            "team_name": None,
        },
        config=_base_config(deps),
    )

    assert result.get("error") is None
    assert result["company_is_new"] is True
    assert result["normalized_ticket"].company_name == "Newco"
    assert result["normalized_ticket"].partner_name == "Laura"
    assert "Cliente nuevo" in result["resolved_fields"].tag_names
    assert any(contact["name"] == "Newco" for contact in odoo_service.contacts)


@pytest.mark.asyncio
async def test_email_con_datos_faltantes_anade_tag_y_descripcion():
    graph = build_ticket_graph()
    deps = _build_deps(
        """{
            "title": "Solicitud poco clara",
            "description": "El cliente pide ayuda pero no concreta nada.",
            "company_name": null,
            "partner_name": null,
            "customer_email": null,
            "team": null,
            "ticket_type": null,
            "category": null,
            "stage": null,
            "tags": [],
            "priority": "normal"
        }"""
    )

    result = await graph.ainvoke(
        {
            "email_subject": "Ayuda",
            "email_body": "Necesito ayuda con algo del sistema.",
            "sender_email": "",
            "sender_name": None,
            "team_name": None,
        },
        config=_base_config(deps),
    )

    assert result.get("error") is None
    assert result["missing_fields"] == ["compania", "tipo de ticket"]
    assert "Faltan datos" in result["resolved_fields"].tag_names
    assert "Datos que faltan:" in result["ticket_vals"]["description"]
    assert "- compania" in result["ticket_vals"]["description"]
    assert "- tipo de ticket" in result["ticket_vals"]["description"]
