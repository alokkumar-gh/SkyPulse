from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.db.session import get_db
from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.core.freshness_policy import format_freshness_label
from app.schemas.map import (
    GeoJSONFeatureCollection,
    GeoJSONFeature,
    GeoJSONGeometry,
)

router = APIRouter(prefix="/map", tags=["Geospatial & Map"])


@router.get("/events", response_model=GeoJSONFeatureCollection)
async def get_map_events(
    category: Optional[str] = Query(None),
    severity: Optional[int] = Query(None, ge=1, le=4),
    status: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(True),
    state: Optional[str] = Query(None),
    time_range: Optional[str] = Query("live"),  # 'live', '1h', '6h', '24h', '7d', 'all'
    hours: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve GeoJSON FeatureCollection of weather events for Live Map visualization.
    Enforces server-authoritative freshness: historical/expired events are strictly excluded
    from the default 'live' view, while preserving historical archive access via time filters.
    """
    server_time = datetime.now(timezone.utc)
    query = select(WeatherEvent).where(
        WeatherEvent.is_deleted == False,
        WeatherEvent.centroid_lat.isnot(None),
        WeatherEvent.centroid_lon.isnot(None),
    )
    if is_active is not None and time_range != "all":
        query = query.where(WeatherEvent.is_active == is_active)
    if category:
        query = query.where(WeatherEvent.category == category.upper())
    if severity:
        query = query.where(WeatherEvent.severity == severity)
    if status:
        query = query.where(WeatherEvent.verification_status == status.upper())
    if state:
        query = query.where(WeatherEvent.primary_state.ilike(f"%{state}%"))

    # Map Time Filtering
    if hours is not None and hours > 0:
        cutoff = server_time - timedelta(hours=hours)
        query = query.where(or_(WeatherEvent.first_reported_at >= cutoff, WeatherEvent.last_updated_at >= cutoff, WeatherEvent.observed_at >= cutoff))
    elif time_range == "1h":
        cutoff = server_time - timedelta(hours=1)
        query = query.where(or_(WeatherEvent.first_reported_at >= cutoff, WeatherEvent.last_updated_at >= cutoff, WeatherEvent.observed_at >= cutoff))
    elif time_range == "6h":
        cutoff = server_time - timedelta(hours=6)
        query = query.where(or_(WeatherEvent.first_reported_at >= cutoff, WeatherEvent.last_updated_at >= cutoff, WeatherEvent.observed_at >= cutoff))
    elif time_range == "24h":
        cutoff = server_time - timedelta(hours=24)
        query = query.where(or_(WeatherEvent.first_reported_at >= cutoff, WeatherEvent.last_updated_at >= cutoff, WeatherEvent.observed_at >= cutoff))
    elif time_range == "7d":
        cutoff = server_time - timedelta(days=7)
        query = query.where(or_(WeatherEvent.first_reported_at >= cutoff, WeatherEvent.last_updated_at >= cutoff, WeatherEvent.observed_at >= cutoff))
    elif time_range == "all":
        # Full historical archive
        pass
    else:  # default: 'live'
        # Must be strictly active, unresolved, and not expired
        query = query.where(
            WeatherEvent.is_active == True,
            WeatherEvent.resolved_at.is_(None),
            or_(
                WeatherEvent.expires_at.is_(None),
                WeatherEvent.expires_at > server_time
            ),
            WeatherEvent.lifecycle_status != "EXPIRED"
        )

    result = await db.execute(query.limit(500))
    raw_events = result.scalars().all()

    deterministic_icons = {
        "RAINFALL": "🌧️",
        "THUNDERSTORM": "⛈️",
        "FLOODING": "🌊",
        "FLOOD": "🌊",
        "HEATWAVE": "🔥",
        "FOG": "🌫️",
        "DUST_STORM": "🌪️",
        "STRONG_WINDS": "💨",
        "WIND": "💨",
        "CYCLONE": "🌀",
        "LANDSLIDE": "⛰️",
        "COLD_WAVE": "❄️",
        "EARTHQUAKE": "🌋",
        "DROUGHT": "☀️",
        "WEATHER": "🌦️",
        "UNKNOWN": "🌦️",
    }

    from app.services.weather_intelligence_service import synthesize_semantic_event_intelligence

    features = []
    for e in raw_events:
        # Enforce server-side category TTL policy check in live mode
        if time_range == "live" or (time_range is None and hours is None):
            eff_exp = e.effective_expires_at
            if eff_exp and server_time >= eff_exp:
                continue
            if e.effective_lifecycle_status == "EXPIRED":
                continue

        icon = deterministic_icons.get((e.category or "WEATHER").upper(), "🌦️")
        semantic_intel = synthesize_semantic_event_intelligence(
            category=e.category,
            sub_category=e.sub_category,
            state=e.primary_state,
            district=e.primary_district,
            city=e.primary_city,
            evidence_texts=[],
            publishers=[],
            evidence_count=e.evidence_count,
        )
        loc_name = f"{e.primary_city or e.primary_district or ''}, {e.primary_state or ''}".strip(", ") or "India"
        phenomenon_label = semantic_intel["phenomenon"].replace("_", " ").title()

        observed_dt = e.effective_observed_at
        features.append(
            GeoJSONFeature(
                type="Feature",
                geometry=GeoJSONGeometry(
                    type="Point",
                    coordinates=[e.centroid_lon, e.centroid_lat],
                ),
                properties={
                    "id": str(e.id),
                    "event_id": str(e.id),
                    "title": semantic_intel["title"],
                    "category": e.category,
                    "sub_category": semantic_intel["sub_category"],
                    "phenomenon": semantic_intel["phenomenon"],
                    "event_nature": semantic_intel["event_nature"],
                    "temporal_scope": semantic_intel["temporal_scope"],
                    "is_current_observation": semantic_intel["is_current_observation"],
                    "evidence_basis": semantic_intel["evidence_basis"],
                    "severity": e.severity,
                    "latitude": e.centroid_lat,
                    "longitude": e.centroid_lon,
                    "location_name": loc_name,
                    "city": e.primary_city,
                    "district": e.primary_district,
                    "state": e.primary_state,
                    "status": e.effective_lifecycle_status,
                    "lifecycle_status": e.effective_lifecycle_status,
                    "verification_status": e.verification_status,
                    "confidence_score": e.confidence_score,
                    "evidence_count": e.evidence_count or 1,
                    "supporting_signal_count": e.evidence_count or 1,
                    "source_count": 1,
                    "independent_source_count": 1,
                    "icon": icon,
                    "label": f"{icon} {phenomenon_label} · {e.primary_district or e.primary_city or e.primary_state or 'India'}",
                    "observed_at": observed_dt.isoformat() if observed_dt else None,
                    "ingested_at": e.effective_ingested_at.isoformat() if e.effective_ingested_at else None,
                    "last_seen_at": e.effective_last_seen_at.isoformat() if e.effective_last_seen_at else None,
                    "expires_at": e.effective_expires_at.isoformat() if e.effective_expires_at else None,
                    "freshness_label": format_freshness_label(observed_dt, server_time),
                    "server_time": server_time.isoformat(),
                    "first_reported_at": e.first_reported_at.isoformat() if e.first_reported_at else None,
                    "last_updated_at": e.last_updated_at.isoformat() if e.last_updated_at else None,
                    "is_anomalous": e.is_anomalous or (semantic_intel["event_nature"] == "ANOMALY"),
                    "is_active": e.is_active and (e.effective_lifecycle_status != "EXPIRED"),
                },
            )
        )
    return GeoJSONFeatureCollection(
        type="FeatureCollection",
        features=features,
        server_time=server_time.isoformat(),
        total_features=len(features),
    )



@router.get("/reports", response_model=GeoJSONFeatureCollection)
async def get_map_reports(
    category: Optional[str] = Query(None),
    severity: Optional[int] = Query(None, ge=1, le=4),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve GeoJSON FeatureCollection of observational weather reports."""
    query = select(WeatherReport).where(
        WeatherReport.is_deleted == False,
        WeatherReport.location_lat.isnot(None),
        WeatherReport.location_lon.isnot(None),
    )
    if category:
        query = query.where(WeatherReport.primary_category == category.upper())
    if severity:
        query = query.where(WeatherReport.severity == severity)

    result = await db.execute(query.order_by(WeatherReport.ingested_at.desc()).limit(limit))
    reports = result.scalars().all()

    features = [
        GeoJSONFeature(
            type="Feature",
            geometry=GeoJSONGeometry(
                type="Point",
                coordinates=[r.location_lon, r.location_lat],
            ),
            properties={
                "id": str(r.id),
                "category": r.primary_category,
                "severity": r.severity,
                "city": r.location_city,
                "district": r.location_district,
                "state": r.location_state,
                "status": r.status,
                "ingested_at": r.ingested_at.isoformat() if r.ingested_at else None,
            },
        )
        for r in reports
    ]
    return GeoJSONFeatureCollection(type="FeatureCollection", features=features)
