import re
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.weather_event import WeatherEvent
from app.models.enums import WeatherCategory, EventSeverity, VerificationStatus


@pytest.mark.asyncio
async def test_full_user_and_reporting_lifecycle(client: AsyncClient):
    # 1. Register a new citizen
    reg_payload = {
        "email": "lifecycle_citizen@skypulse.gov.in",
        "password": "StrongPassword123!",
        "display_name": "Lifecycle Citizen",
        "phone_number": "+919876543211",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    # 2. Login to get access token
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": reg_payload["email"], "password": reg_payload["password"]},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Submit a weather report
    report_payload = {
        "description": "Intense lightning and gale winds witnessed across Marine Drive",
        "event_type": "THUNDERSTORM",
        "severity": 3,
        "latitude": 18.9438,
        "longitude": 72.8232,
        "location_name": "Marine Drive, Mumbai",
    }
    report_res = await client.post("/api/v1/reports", json=report_payload, headers=headers)
    assert report_res.status_code == 201
    report_data = report_res.json()
    report_id = report_data["id"]
    tracking_id = report_data["tracking_id"]
    assert re.match(r"^SP-\d{4}-\d{6}$", tracking_id)

    # 4. Fetch the report by ID
    get_res = await client.get(f"/api/v1/reports/{report_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["primary_category"] == "THUNDERSTORM"
    assert get_res.json()["location"]["lat"] == 18.9438

    # 5. Query map reports GeoJSON
    map_rep_res = await client.get("/api/v1/map/reports?category=THUNDERSTORM")
    assert map_rep_res.status_code == 200
    features = map_rep_res.json()["features"]
    assert any(f["properties"]["id"] == report_id for f in features)

    # 6. National analytics
    analytics_res = await client.get("/api/v1/analytics/national")
    assert analytics_res.status_code == 200
    assert analytics_res.json()["total_reports"] >= 1


@pytest.mark.asyncio
async def test_analyst_verification_workflow(
    client: AsyncClient, test_analyst: User, auth_headers, db_session: AsyncSession
):
    # Seed an event requiring review
    event = WeatherEvent(
        category=WeatherCategory.CYCLONE.value,
        severity=EventSeverity.CATASTROPHIC.value,
        primary_state="Odisha",
        primary_district="Puri",
        centroid_lat=19.8135,
        centroid_lon=85.8312,
        verification_status=VerificationStatus.REQUIRES_REVIEW.value,
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    headers = auth_headers(test_analyst)

    # 1. Analyst inspects verification queue
    queue_res = await client.get("/api/v1/verification/queue", headers=headers)
    assert queue_res.status_code == 200
    q_items = queue_res.json()["results"]
    assert any(item["event_id"] == str(event.id) for item in q_items)

    # 2. Analyst views verification detail
    detail_res = await client.get(f"/api/v1/verification/{event.id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["status"] == "REQUIRES_REVIEW"

    # 3. Analyst applies manual override
    override_payload = {
        "status": "VERIFIED",
        "reason": "Confirmed against IMD Doppler Weather Radar observations and coastal buoy data",
    }
    ov_res = await client.post(
        f"/api/v1/verification/{event.id}/override",
        json=override_payload,
        headers=headers,
    )
    assert ov_res.status_code == 200
    ov_data = ov_res.json()
    assert ov_data["status"] == "VERIFIED"
    assert ov_data["is_manual_override"] is True

    # 4. Check canonical event status updated
    event_res = await client.get(f"/api/v1/events/{event.id}")
    assert event_res.status_code == 200
    assert event_res.json()["verification_status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_consistent_error_response_envelope(client: AsyncClient):
    # 401 Unauthorized
    res_401 = await client.get("/api/v1/auth/me")
    assert res_401.status_code == 401
    d_401 = res_401.json()
    assert "error" in d_401 and "message" in d_401 and "details" in d_401

    # 404 Not Found
    res_404 = await client.get("/api/v1/events/00000000-0000-0000-0000-000000000000")
    assert res_404.status_code == 404
    d_404 = res_404.json()
    assert "error" in d_404 and "message" in d_404 and "details" in d_404

    # 422 Unprocessable Entity
    res_422 = await client.post("/api/v1/auth/register", json={"email": "bad_email"})
    assert res_422.status_code == 422
    d_422 = res_422.json()
    assert "error" in d_422 and "message" in d_422 and "details" in d_422
    assert d_422["error"] == "VALIDATION_ERROR"
