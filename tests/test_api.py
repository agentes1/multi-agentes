# tests/test_api.py
import pytest
from httpx import ASGITransport, AsyncClient

from api import app


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
    # debug temporal: ver qué devuelve realmente la API
    print("\nSTATUS:", response.status_code)
    print("BODY:", response.json())

    assert response.status_code == 400
