import pytest
from httpx import ASGITransport, AsyncClient

from api import app
import pipeline
from agents.budget_agent.dependencies import BudgetDependencies
from agents.intake_agent.dependencies import IntakeDependencies


class MockLLMValid:
    async def ainvoke(self, messages):
        class Response:
            content = """{
                \"company_name\": \"Acme SL\",
                \"project_summary\": \"Necesitan CRM y facturación\",
                \"requirements\": [\"crm\", \"presupuestos\"],
                \"urgency\": \"alta\",
                \"ticket_type\": \"budget\",
                \"missing_information\": []
            }"""

        return Response()


class MockMemoryStore:
    def get_last_quote_memory(self, company_name):
        class Memory:
            quote_count = 0
            last_quote_total = 0.0

            def model_dump(self):
                return {"quote_count": 0, "last_quote_total": 0.0}

        return Memory()

    def append_quote(self, item):
        pass

    def now_iso(self):
        return "2025-01-01T00:00:00"


class MockMCPService:
    async def get_budget_context(self, company_name, product_codes):
        return {
            "customer_profile": {"name": company_name, "discount": 0},
            "quote": {
                "company_name": company_name,
                "lines": [
                    {"code": "crm_base", "name": "CRM base", "unit_price": 1000.0, "quantity": 1},
                    {
                        "code": "presupuestos",
                        "name": "Módulo de presupuestos",
                        "unit_price": 2000.0,
                        "quantity": 1,
                    },
                ],
                "subtotal": 3000.0,
                "discount_amount": 300.0,
                "total": 2700.0,
                "currency": "EUR",
                "warnings": [],
            },
        }


class MockOdooService:
    def create_helpdesk_ticket(self, **kwargs):
        return 1

    def get_helpdesk_ticket(self, ticket_id):
        return {"id": ticket_id}

    def get_team_id_by_name(self, name):
        return 1

    def get_ticket_type_id_by_name(self, name):
        return 1

    def get_category_id_by_name(self, name):
        return 1

    def get_tag_ids_by_names(self, names):
        return []

    def get_motive_id_by_name_and_team(self, name, team_id):
        return None


def _build_intake_deps(model: str | None = None) -> IntakeDependencies:
    _ = model
    return IntakeDependencies(llm=MockLLMValid(), odoo_service=MockOdooService())


def _build_budget_deps(model: str | None = None) -> BudgetDependencies:
    _ = model
    return BudgetDependencies(
        llm=MockLLMValid(),
        memory_store=MockMemoryStore(),
        mcp_service=MockMCPService(),
    )


@pytest.fixture(autouse=True)
def patch_pipeline_dependencies(monkeypatch):
    monkeypatch.setattr(pipeline, "build_intake_deps", _build_intake_deps)
    monkeypatch.setattr(pipeline, "build_budget_deps", _build_budget_deps)


@pytest.mark.asyncio
async def test_process_email_valido():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/process",
            json={
                "source_input": {
                    "channel": "email",
                    "from": "cliente@acme.com",
                    "subject": "Presupuesto ERP",
                    "body": "Somos Acme SL, necesitamos CRM y facturación.",
                }
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["normalized_request"]["company_name"] == "Acme SL"
    assert data["final_text"] != ""


@pytest.mark.asyncio
async def test_process_email_vacio_devuelve_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/process",
            json={
                "source_input": {
                    "channel": "email",
                    "from": "test@test.com",
                    "subject": "",
                    "body": "",
                }
            },
        )
    assert response.status_code == 400
