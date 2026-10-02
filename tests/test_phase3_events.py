import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weather_event import WeatherEvent
from app.models.enums import WeatherCategory, EventSeverity, VerificationStatus


@pytest.mark.asyncio
async def test_list_and_filter_events(client: AsyncClient, db_session: AsyncSession):
    # Seed canonical events
    e1 = WeatherEvent(
        category=WeatherCategory.RAINFALL.value,
        severity=EventSeverity.SEVERE.value,
        primary_state="Maharashtra",
        primary_district="Mumbai",
        centroid_lat=19.0760,
        centroid_lon=72.8777,
        verification_status=VerificationStatus.VERIFIED.value,
        is_active=True,
    )
    e2 = WeatherEvent(
        category=WeatherCategory.FOG.value,
        severity=EventSeverity.LOW.value,
        primary_state="Delhi",
        primary_district="New Delhi",
        centroid_lat=28.6139,
        centroid_lon=77.2090,
        verification_status=VerificationStatus.UNVERIFIED.value,
        is_active=True,
    )
    db_session.add_all([e1, e2])
    await db_session.commit()
    await db_session.refresh(e1)
    await db_session.refresh(e2)

    # 1. List all
    res = await client.get("/api/v1/events")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 2
    assert "results" in data

    # 2. Filter by category
    res_cat = await client.get("/api/v1/events?category=RAINFALL")
    assert res_cat.status_code == 200
    data_cat = res_cat.json()
    assert all(ev["category"] == "RAINFALL" for ev in data_cat["results"])

    # 3. Filter by state
    res_state = await client.get("/api/v1/events?state=Delhi")
    assert res_state.status_code == 200
    data_state = res_state.json()
    assert any(ev["id"] == str(e2.id) for ev in data_state["results"])


@pytest.mark.asyncio
async def test_get_single_event_and_timeline(client: AsyncClient, db_session: AsyncSession):
    event = WeatherEvent(
        category=WeatherCategory.THUNDERSTORM.value,
        severity=EventSeverity.MODERATE.value,
        primary_state="Karnataka",
        primary_district="Bengaluru Urban",
        centroid_lat=12.9716,
        centroid_lon=77.5946,
        verification_status=VerificationStatus.LIKELY.value,
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    # Single event
    res = await client.get(f"/api/v1/events/{event.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(event.id)
    assert data["category"] == "THUNDERSTORM"
    assert data["location"]["district"] == "Bengaluru Urban"

    # Timeline
    tl_res = await client.get(f"/api/v1/events/{event.id}/timeline")
    assert tl_res.status_code == 200
    tl_data = tl_res.json()
    assert tl_data["event_id"] == str(event.id)
    assert isinstance(tl_data["timeline"], list)


@pytest.mark.asyncio
async def test_nearby_events(client: AsyncClient, db_session: AsyncSession):
    # Bengaluru event
    event = WeatherEvent(
        category=WeatherCategory.RAINFALL.value,
        severity=EventSeverity.MODERATE.value,
        primary_state="Karnataka",
        primary_district="Bengaluru",
        centroid_lat=12.9716,
        centroid_lon=77.5946,
        verification_status=VerificationStatus.VERIFIED.value,
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()

    # Query near Bengaluru (lat=12.97, lon=77.59, radius=20km)
    res = await client.get("/api/v1/events/nearby?lat=12.97&lon=77.59&radius_km=30")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "distance_km" in data[0]
    assert data[0]["distance_km"] <= 30.0


@pytest.mark.asyncio
async def test_get_nonexistent_event(client: AsyncClient):
    res = await client.get("/api/v1/events/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404
    data = res.json()
    assert data["error"] == "EVENT_NOT_FOUND"
