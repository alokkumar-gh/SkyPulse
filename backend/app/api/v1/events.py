import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.dependencies import get_optional_current_user
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.event import (
    EventSummary,
    EventDetail,
    EventTimeline,
    NearbyEvent,
)
from app.schemas.dna import (
    EventDNAResponse,
    EventDNASnapshot,
    EvidenceFingerprint,
    DNAPropagationProfile,
    DNATimelineEntry,
)
from app.services.event_service import (
    list_events,
    get_event_by_id,
    get_event_timeline,
    get_nearby_events,
)
from app.services.event_dna_service import event_dna_service

router = APIRouter(prefix="/events", tags=["Weather Events"])


def _parse_uuid_or_400(event_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_UUID",
                "message": f"Provided event ID '{event_id}' is not a valid UUID",
                "details": {"event_id": event_id},
            },
        )


@router.get("", response_model=PaginatedResponse[EventSummary])
async def get_weather_events(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    severity: Optional[int] = Query(None, ge=1, le=4),
    severity_min: Optional[int] = Query(None, ge=1, le=4),
    status: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_anomalous: Optional[bool] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    max_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    min_evidence_count: Optional[int] = Query(None, ge=1),
    has_propagation: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve canonical weather events with multidimensional DNA filtering."""
    events, total = await list_events(
        db=db,
        page=page,
        per_page=per_page,
        q=q,
        category=category,
        severity=severity,
        severity_min=severity_min,
        status=status,
        state=state,
        district=district,
        is_active=is_active,
        is_anomalous=is_anomalous,
        from_date=from_date,
        to_date=to_date,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        min_evidence_count=min_evidence_count,
        has_propagation=has_propagation,
    )
    return PaginatedResponse.build(items=events, total=total, page=page, per_page=per_page)


@router.get("/changes")
async def get_event_changes(
    since: Optional[str] = Query(None, description="ISO timestamp or client revision for delta sync"),
    db: AsyncSession = Depends(get_db),
):
    """
    Delta synchronization endpoint (Section 10).
    Returns incremental changes: created, updated, expired, deactivated, server_time, revision.
    Eliminates redundant full-dataset downloads during fallback polling.
    """
    from datetime import timezone, timedelta
    from sqlalchemy import select, or_
    from app.models.weather_event import WeatherEvent

    server_time = datetime.now(timezone.utc)
    since_dt = None
    if since:
        try:
            cleaned = since.replace("Z", "+00:00")
            since_dt = datetime.fromisoformat(cleaned)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except Exception:
            since_dt = None

    def _event_dict(e: WeatherEvent) -> dict:
        obs_dt = e.effective_observed_at
        ing_dt = e.effective_ingested_at
        seen_dt = e.effective_last_seen_at
        exp_dt = e.effective_expires_at
        return {
            "id": str(e.id),
            "event_id": str(e.id),
            "category": e.category,
            "sub_category": e.sub_category,
            "severity": e.severity,
            "confidence": e.confidence_score,
            "confidence_score": e.confidence_score,
            "verification_status": e.verification_status,
            "status": e.effective_lifecycle_status,
            "lifecycle_status": e.effective_lifecycle_status,
            "state": e.primary_state,
            "district": e.primary_district,
            "city": e.primary_city,
            "latitude": e.centroid_lat,
            "longitude": e.centroid_lon,
            "location": {
                "state": e.primary_state,
                "district": e.primary_district,
                "city": e.primary_city,
                "lat": e.centroid_lat,
                "lon": e.centroid_lon,
            },
            "observed_at": obs_dt.isoformat() if obs_dt else None,
            "ingested_at": ing_dt.isoformat() if ing_dt else None,
            "last_seen_at": seen_dt.isoformat() if seen_dt else None,
            "expires_at": exp_dt.isoformat() if exp_dt else None,
            "first_reported_at": e.first_reported_at.isoformat() if e.first_reported_at else None,
            "last_updated_at": e.last_updated_at.isoformat() if e.last_updated_at else None,
            "evidence_count": e.evidence_count,
            "supporting_signal_count": e.evidence_count,
            "source_count": 1,
            "is_active": e.is_active and (e.effective_lifecycle_status != "EXPIRED"),
            "is_anomalous": e.is_anomalous,
        }

    created_events = []
    updated_events = []
    expired_ids = []
    deactivated_ids = []

    if since_dt is None:
        # Initial synchronization: return all fresh active events as created
        q = select(WeatherEvent).where(
            WeatherEvent.is_deleted == False,
            WeatherEvent.is_active == True,
            WeatherEvent.resolved_at.is_(None),
            or_(WeatherEvent.expires_at.is_(None), WeatherEvent.expires_at > server_time),
            WeatherEvent.lifecycle_status != "EXPIRED",
        ).limit(300)
        res = await db.execute(q)
        for e in res.scalars().all():
            if e.effective_lifecycle_status != "EXPIRED":
                created_events.append(_event_dict(e))
    else:
        # Delta mode: fetch events modified, created, or resolved since since_dt
        q = select(WeatherEvent).where(
            or_(
                WeatherEvent.last_updated_at >= since_dt,
                WeatherEvent.created_at >= since_dt,
                WeatherEvent.updated_at >= since_dt,
                WeatherEvent.resolved_at >= since_dt,
            )
        ).limit(300)
        res = await db.execute(q)
        for e in res.scalars().all():
            if e.is_deleted or not e.is_active:
                deactivated_ids.append(str(e.id))
            elif e.effective_lifecycle_status == "EXPIRED":
                expired_ids.append(str(e.id))
            elif e.created_at and e.created_at >= since_dt and e.evidence_count <= 1:
                created_events.append(_event_dict(e))
            else:
                updated_events.append(_event_dict(e))

    revision = int(server_time.timestamp() * 1000)
    return {
        "created": created_events,
        "updated": updated_events,
        "expired": expired_ids,
        "deactivated": deactivated_ids,
        "revision": revision,
        "server_time": server_time.isoformat(),
    }


@router.get("/nearby", response_model=List[NearbyEvent])
async def search_nearby_events(
    lat: float = Query(..., ge=6.5, le=37.6),
    lon: float = Query(..., ge=68.0, le=97.5),
    radius_km: float = Query(50.0, ge=1.0, le=500.0),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Geospatial proximity search for canonical events within a radial distance (km)."""
    return await get_nearby_events(
        db=db,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        limit=limit,
    )


# -----------------------------------------------------------------------------
# WEATHER EVENT DNA ENDPOINTS
# -----------------------------------------------------------------------------

@router.get("/{event_id}/dna", response_model=EventDNAResponse)
async def get_weather_event_dna(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Retrieve the complete, persistent Weather Event DNA representation.
    Answers: What is this event, why do we believe it, origin, evolution, evidence footprint,
    contradictions, and propagation history.
    """
    _parse_uuid_or_400(event_id)
    user_role = current_user.role if current_user else "PUBLIC"
    dna = await event_dna_service.get_event_dna(event_id=event_id, db=db, role=user_role)
    if not dna:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EVENT_NOT_FOUND",
                "message": f"Event DNA for event ID {event_id} was not found",
                "details": {"event_id": event_id},
            },
        )
    return dna


@router.get("/{event_id}/dna/timeline", response_model=List[DNATimelineEntry])
async def get_weather_event_dna_timeline(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Retrieve the chronological evolution and milestone journey of an Event DNA."""
    _parse_uuid_or_400(event_id)
    user_role = current_user.role if current_user else "PUBLIC"
    dna = await event_dna_service.get_event_dna(event_id=event_id, db=db, role=user_role)
    if not dna:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EVENT_NOT_FOUND",
                "message": f"Event DNA for event ID {event_id} was not found",
                "details": {"event_id": event_id},
            },
        )
    return dna.timeline


@router.get("/{event_id}/dna/evidence", response_model=EvidenceFingerprint)
async def get_weather_event_dna_evidence(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Retrieve the multi-source evidence footprint and corroboration breakdown."""
    _parse_uuid_or_400(event_id)
    user_role = current_user.role if current_user else "PUBLIC"
    dna = await event_dna_service.get_event_dna(event_id=event_id, db=db, role=user_role)
    if not dna:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EVENT_NOT_FOUND",
                "message": f"Event DNA for event ID {event_id} was not found",
                "details": {"event_id": event_id},
            },
        )
    return dna.evidence


@router.get("/{event_id}/dna/propagation", response_model=DNAPropagationProfile)
async def get_weather_event_dna_propagation(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Retrieve recorded physical propagation trajectory stages derived from DWEG."""
    _parse_uuid_or_400(event_id)
    user_role = current_user.role if current_user else "PUBLIC"
    dna = await event_dna_service.get_event_dna(event_id=event_id, db=db, role=user_role)
    if not dna:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EVENT_NOT_FOUND",
                "message": f"Event DNA for event ID {event_id} was not found",
                "details": {"event_id": event_id},
            },
        )
    return dna.propagation


@router.get("/{event_id}/dna/snapshot", response_model=EventDNASnapshot)
async def get_weather_event_dna_snapshot(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Retrieve compact event DNA fingerprint snapshot for dashboard widgets."""
    _parse_uuid_or_400(event_id)
    user_role = current_user.role if current_user else "PUBLIC"
    dna = await event_dna_service.get_event_dna(event_id=event_id, db=db, role=user_role)
    if not dna:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EVENT_NOT_FOUND",
                "message": f"Event DNA for event ID {event_id} was not found",
                "details": {"event_id": event_id},
            },
        )
    return dna.snapshot


# -----------------------------------------------------------------------------
# STANDARD EVENT DETAILS & LEGACY TIMELINE
# -----------------------------------------------------------------------------

@router.get("/{event_id}", response_model=EventDetail)
async def get_single_weather_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get complete details, evidence links, and verification status of a canonical event."""
    e_uuid = _parse_uuid_or_400(event_id)
    event = await get_event_by_id(db=db, event_id=e_uuid)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EVENT_NOT_FOUND",
                "message": f"Canonical weather event with ID {event_id} was not found",
                "details": {"event_id": event_id},
            },
        )
    return event


@router.get("/{event_id}/timeline", response_model=EventTimeline)
async def get_single_event_timeline(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the chronological sequence of corroborating and contradicting evidence reports."""
    e_uuid = _parse_uuid_or_400(event_id)
    timeline = await get_event_timeline(db=db, event_id=e_uuid)
    if not timeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EVENT_NOT_FOUND",
                "message": f"Canonical weather event with ID {event_id} was not found",
                "details": {"event_id": event_id},
            },
        )
    return timeline
