"""
SkyPulse Recent Weather Intelligence Portal API Router
======================================================
Exposes public and authenticated endpoints for the SkyPulse Portal:
- GET /api/v1/weather/recent
- GET /api/v1/weather/events
- GET /api/v1/weather/events/{id}
- GET /api/v1/weather/map
- GET /api/v1/weather/stats
- GET /api/v1/weather/sources
- GET /api/v1/weather/timeline
- GET /api/v1/weather/search
- GET /api/v1/weather/alerts
- GET /api/v1/weather/health
- GET /api/v1/weather/ingestion/status
- POST /api/v1/weather/ingestion/trigger
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.dependencies import get_optional_current_user, get_current_user, require_role
from app.models.user import User
from app.services.weather_intelligence_service import weather_intelligence_service
from app.services.auto_fetch_manager import auto_fetch_manager
from ai.opensearch_indexer import opensearch_indexer
from app.services.dweg_service import dweg_service
from connectors.weather_discovery.regional_rss import RSS_FEEDS

logger = logging.getLogger("skypulse.api.weather")

router = APIRouter(prefix="/weather", tags=["Recent Weather Intelligence"])


@router.get("/recent")
async def get_recent_weather_feed(
    freshness: Optional[str] = Query(None, description="BREAKING (0-6h), RECENT (6-24h), TODAY (24-48h), HISTORICAL (>48h), or ALL"),
    time_range: Optional[str] = Query("24h", description="1h, 6h, 12h, 24h, 48h, 7d, all"),
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    severity: Optional[int] = Query(None, ge=1, le=4),
    verification_status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve recent canonical weather intelligence feed with evidence provenance and freshness bucketing."""
    return await weather_intelligence_service.get_recent_feed(
        db=db,
        freshness=freshness,
        time_range=time_range,
        state=state,
        district=district,
        city=city,
        category=category,
        severity=severity,
        verification_status=verification_status,
        limit=limit,
        offset=offset,
    )


@router.get("/intelligence/latest")
async def get_latest_weather_intelligence(
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    freshness: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Section 19: LATEST WEATHER INTELLIGENCE.
    Returns newest-first publication feed with geographic & source diversity re-ranking,
    complete Section 24 contract, and honest freshness status.
    """
    return await weather_intelligence_service.get_latest_weather_intelligence(
        db=db,
        state=state,
        district=district,
        category=category,
        freshness=freshness,
        limit=limit,
        offset=offset,
    )


@router.get("/events")
async def get_weather_events(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    severity: Optional[int] = Query(None, ge=1, le=4),
    verification_status: Optional[str] = Query(None),
    time_range: Optional[str] = Query("all"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Paginated list of canonical weather events across India."""
    offset = (page - 1) * per_page
    res = await weather_intelligence_service.get_recent_feed(
        db=db,
        time_range=time_range,
        state=state,
        district=district,
        category=category,
        severity=severity,
        verification_status=verification_status,
        limit=per_page,
        offset=offset,
    )
    total = res["total"]
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
        "events": res["events"],
    }


@router.get("/events/{event_id}")
async def get_weather_event_by_id(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Fetch complete canonical event details, multi-source evidence links, and verification breakdown."""
    detail = await weather_intelligence_service.get_event_detail(event_id=event_id, db=db)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EVENT_NOT_FOUND",
                "message": f"Canonical weather event with ID '{event_id}' was not found.",
                "details": {"event_id": event_id},
            },
        )
    return detail


@router.get("/map")
async def get_weather_map(
    category: Optional[str] = Query(None),
    severity: Optional[int] = Query(None, ge=1, le=4),
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    window: Optional[str] = Query(None),
    time_range: Optional[str] = Query(None),
    hours: Optional[int] = Query(None, ge=1, le=168),
    layers: Optional[str] = Query(None),
    zoom: int = Query(5, ge=1, le=18),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Unified multi-layer geospatial points for map rendering across India.
    Includes Observations (AWS), Canonical Events, Official Warnings, and News.
    Strictly excludes fabricated coordinates.
    """
    return await weather_intelligence_service.get_map_data(
        db=db,
        category=category,
        severity=severity,
        state=state,
        district=district,
        window=window,
        time_range=time_range,
        hours=hours,
        layers=layers,
        zoom=zoom,
    )


@router.get("/coverage")
async def get_weather_coverage(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """National geographic coverage audit across Indian states, districts, and stations."""
    return await weather_intelligence_service.get_coverage_data(db=db)


@router.get("/stats")
async def get_weather_statistics(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregated operational statistics and analytics across Indian weather intelligence."""
    return await weather_intelligence_service.get_statistics(db=db)


@router.get("/sources")
async def get_weather_sources(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Comprehensive list of registered sources, feeds, and health statuses."""
    return await weather_intelligence_service.get_registered_sources(db=db)


@router.get("/sources/health")
async def get_weather_sources_health(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Section 27: SOURCE HEALTH PANEL.
    Provides operational metrics per source: fetch status, articles fetched, duplicates, errors, state & district coverage.
    """
    return await weather_intelligence_service.get_source_health_panel(db=db)


@router.get("/timeline")
async def get_weather_timeline(
    state: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Chronological event timeline for recent Indian weather incidents."""
    res = await weather_intelligence_service.get_recent_feed(
        db=db,
        state=state,
        category=category,
        time_range="7d",
        limit=limit,
    )
    return {
        "timeline_events": res["events"],
        "total": res["total"],
    }


@router.get("/search")
async def search_weather(
    q: str = Query(..., min_length=2, description="Search term for city, district, state, or event keyword"),
    state: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Search weather intelligence using OpenSearch with PostgreSQL fallback."""
    return await weather_intelligence_service.search_events(
        query=q,
        db=db,
        state=state,
        category=category,
        limit=limit,
    )


@router.get("/alerts")
async def get_active_weather_alerts(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Retrieve active severe weather alerts, cyclones, floods, and government warnings."""
    return await weather_intelligence_service.get_active_alerts(db=db, limit=limit)


@router.get("/health")
async def get_weather_intelligence_health(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Detailed health check of weather intelligence components."""
    # Check DB
    db_ok = True
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    return {
        "status": "HEALTHY" if db_ok else "DEGRADED",
        "components": {
            "database": "CONNECTED" if db_ok else "ERROR",
            "opensearch": "ONLINE" if opensearch_indexer.is_live else "FALLBACK_IN_MEMORY",
            "neo4j_dweg": "ONLINE" if getattr(dweg_service, "is_live", False) else "FALLBACK_IN_MEMORY",
            "regional_rss_feeds": f"{len(RSS_FEEDS)} registered",
            "auto_fetch_engine": auto_fetch_manager.status,
        },
    }


@router.get("/ingestion/status")
async def get_ingestion_status() -> Dict[str, Any]:
    """Section 30 status response for auto-fetch engine and source health."""
    return auto_fetch_manager.get_status()


@router.post("/ingestion/trigger")
async def trigger_ingestion_cycle(
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> Dict[str, Any]:
    """
    Cloud Scheduler and Admin on-demand ingestion trigger endpoint.
    Executes a multi-layer auto-fetch cycle concurrently.
    """
    # Execute immediately
    result = await auto_fetch_manager.run_single_cycle(
        gnews_query_limit=15,
        rss_item_limit=15,
    )
    return {
        "status": "ACCEPTED",
        "message": "Auto-fetch ingestion cycle executed successfully.",
        "cycle_summary": result,
    }


@router.get("/districts")
async def get_district_weather(
    state: Optional[str] = Query(None, description="Filter by Indian State / UT"),
    district: Optional[str] = Query(None, description="Filter by District name"),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Continuous meteorological observations across Indian districts.
    Returns physical measurements (temp, humidity, rain, wind) with source provenance and freshness tiers.
    """
    from app.services.district_weather_service import district_weather_service
    return await district_weather_service.get_district_weather_list(db=db, state=state, district=district)


@router.get("/telemetry/location")
async def get_location_telemetry(
    state: Optional[str] = Query(None, description="State name"),
    district: Optional[str] = Query(None, description="District name"),
    city: Optional[str] = Query(None, description="City name"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Implements Requirements 20 & 22 (News -> Weather Fallback):
    - Priority 1: Fresh canonical severe weather event / news
    - Priority 2: Latest valid weather observation
    - Priority 3: Honest NO CURRENT TELEMETRY state
    """
    from app.services.district_weather_service import district_weather_service
    return await district_weather_service.get_location_fallback_telemetry(
        db=db, state=state, district=district, city=city
    )


@router.get("/cities")
async def get_city_weather(
    state: Optional[str] = Query(None, description="Filter by State"),
    district: Optional[str] = Query(None, description="Filter by District"),
    city: Optional[str] = Query(None, description="Filter by City name"),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Continuous meteorological observations across Indian cities and municipal stations.
    """
    from app.services.district_weather_service import district_weather_service
    districts = await district_weather_service.get_district_weather_list(db=db, state=state)
    output = []
    for d in districts:
        c_name = d.get("city") or d.get("district_name")
        if city and c_name and city.lower() not in c_name.lower():
            continue
        if district and d.get("district_name") and district.lower() not in d["district_name"].lower():
            continue
        output.append({
            "city": c_name,
            "district": d.get("district_name"),
            "state": d.get("state"),
            "latitude": d.get("latitude"),
            "longitude": d.get("longitude"),
            "weather": d.get("weather"),
            "source": d.get("source"),
            "warning_status": d.get("warning_status"),
        })
    return output


@router.get("/observations/map")
async def get_map_observations(
    zoom: int = Query(5, ge=1, le=18, description="Current map zoom level"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    GeoJSON FeatureCollection representing the routine weather observation layer.
    Visually styled as neutral weather chips on the map (e.g. 29°C ⛅), separate from hazard incident markers.
    """
    from app.services.district_weather_service import district_weather_service
    return await district_weather_service.get_map_observations_layer(db=db, zoom=zoom)


@router.post("/districts/refresh")
async def refresh_district_observations(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> Dict[str, Any]:
    """
    On-demand batch telemetry refresh for all Indian district centroids from Open-Meteo.
    """
    from app.services.district_weather_service import district_weather_service
    return await district_weather_service.refresh_all_districts(db=db)


