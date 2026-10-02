import re
import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_create_report_success(client: AsyncClient, test_citizen: User, auth_headers):
    headers = auth_headers(test_citizen)
    payload = {
        "description": "Continuous heavy rainfall causing waterlogging near Dadar station",
        "event_type": "FLOODING",
        "severity": 3,
        "latitude": 19.0178,
        "longitude": 72.8478,
        "location_name": "Dadar, Mumbai, Maharashtra",
    }
    response = await client.post("/api/v1/reports", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert "tracking_id" in data
    assert data["status"] == "PENDING"
    # Tracking ID format check: SP-YYYY-NNNNNN
    assert re.match(r"^SP-\d{4}-\d{6}$", data["tracking_id"]) is not None


@pytest.mark.asyncio
async def test_create_report_out_of_india_latitude(client: AsyncClient):
    payload = {
        "description": "Blizzard in Europe",
        "event_type": "SNOWFALL",
        "latitude": 51.5074,  # London
        "longitude": 77.2090,
    }
    response = await client.post("/api/v1/reports", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_report_out_of_india_longitude(client: AsyncClient):
    payload = {
        "description": "Storm in Pacific",
        "event_type": "THUNDERSTORM",
        "latitude": 19.0760,
        "longitude": 140.0,  # Far east Pacific
    }
    response = await client.post("/api/v1/reports", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_report_invalid_category(client: AsyncClient):
    payload = {
        "description": "Unregistered phenomenon",
        "event_type": "VOLCANIC_ERUPTION",
        "latitude": 19.0760,
        "longitude": 72.8777,
    }
    response = await client.post("/api/v1/reports", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_list_and_get_report(client: AsyncClient):
    # Submit report first
    payload = {
        "description": "High temperature alert in Ahmedabad",
        "event_type": "HEATWAVE",
        "severity": 3,
        "latitude": 23.0225,
        "longitude": 72.5714,
        "location_name": "Ahmedabad, Gujarat",
    }
    create_res = await client.post("/api/v1/reports", json=payload)
    assert create_res.status_code == 201
    report_id = create_res.json()["id"]

    # Query list
    list_res = await client.get("/api/v1/reports?category=HEATWAVE")
    assert list_res.status_code == 200
    list_data = list_res.json()

    assert "total" in list_data
    assert "page" in list_data
    assert "per_page" in list_data
    assert "pages" in list_data
    assert "results" in list_data
    assert list_data["total"] >= 1
    assert any(r["id"] == report_id for r in list_data["results"])

    # Query single report
    single_res = await client.get(f"/api/v1/reports/{report_id}")
    assert single_res.status_code == 200
    single_data = single_res.json()
    assert single_data["id"] == report_id
    assert single_data["primary_category"] == "HEATWAVE"


@pytest.mark.asyncio
async def test_get_nonexistent_report(client: AsyncClient):
    response = await client.get("/api/v1/reports/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "REPORT_NOT_FOUND"
