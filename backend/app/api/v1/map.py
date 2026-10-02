from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.db.session import get_db
from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
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
    db: AsyncSession = Depends(get_db),
):
    """Retrieve GeoJSON FeatureCollection of weather events for Mapbox/Leaflet visualization."""
    query = select(WeatherEvent).where(
        WeatherEvent.is_deleted == False,
        WeatherEvent.centroid_lat.isnot(None),
        WeatherEvent.centroid_lon.isnot(None),
    )
    if is_active is not None:
        query = query.where(WeatherEvent.is_active == is_active)
    if category:
        query = query.where(WeatherEvent.category == category.upper())
    if severity:
        query = query.where(WeatherEvent.severity == severity)
    if status:
        query = query.where(WeatherEvent.verification_status == status.upper())
    if state:
        query = query.where(WeatherEvent.primary_state.ilike(f"%{state}%"))

    result = await db.execute(query.limit(500))
    events = result.scalars().all()

    features = [
        GeoJSONFeature(
            type="Feature",
            geometry=GeoJSONGeometry(
                type="Point",
                coordinates=[e.centroid_lon, e.centroid_lat],
            ),
            properties={
                "id": str(e.id),
                "category": e.category,
                "severity": e.severity,
                "verification_status": e.verification_status,
                "confidence_score": e.confidence_score,
                "evidence_count": e.evidence_count,
                "city": e.primary_city,
                "district": e.primary_district,
                "state": e.primary_state,
                "first_reported_at": e.first_reported_at.isoformat() if e.first_reported_at else None,
                "is_anomalous": e.is_anomalous,
            },
        )
        for e in events
    ]
    return GeoJSONFeatureCollection(type="FeatureCollection", features=features)


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
