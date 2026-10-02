import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weather_event import WeatherEvent
from app.models.enums import WeatherCategory, EventSeverity, VerificationStatus


@pytest.mark.asyncio
async def test_national_analytics(client: AsyncClient, db_session: AsyncSession):
    event = WeatherEvent(
        category=WeatherCategory.HEATWAVE.value,
        severity=EventSeverity.SEVERE.value,
        primary_state="Rajasthan",
        primary_district="Jaipur",
        verification_status=VerificationStatus.VERIFIED.value,
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()

    res = await client.get("/api/v1/analytics/national")
    assert res.status_code == 200
    data = res.json()

    assert "period" in data
    assert "total_events" in data
    assert "active_events" in data
    assert "by_category" in data
    assert "by_verification_status" in data
    assert "by_severity" in data
    assert "top_states" in data
    assert isinstance(data["top_states"], list)
    assert data["total_events"] >= 1


@pytest.mark.asyncio
async def test_state_analytics(client: AsyncClient, db_session: AsyncSession):
    event = WeatherEvent(
        category=WeatherCategory.FLOODING.value,
        severity=EventSeverity.CATASTROPHIC.value,
        primary_state="Assam",
        primary_district="Guwahati",
        verification_status=VerificationStatus.VERIFIED.value,
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()

    res = await client.get("/api/v1/analytics/state/Assam")
    assert res.status_code == 200
    data = res.json()

    assert data["state"] == "Assam"
    assert data["total_events"] >= 1
    assert "top_districts" in data
    assert isinstance(data["top_districts"], list)


@pytest.mark.asyncio
async def test_timeseries_analytics(client: AsyncClient):
    res = await client.get("/api/v1/analytics/timeseries?metric=events&interval=hourly&days=1")
    assert res.status_code == 200
    data = res.json()

    assert data["metric"] == "events"
    assert data["interval"] == "hourly"
    assert "series" in data
    assert len(data["series"]) >= 1
    assert "timestamp" in data["series"][0]
    assert "value" in data["series"][0]
