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
    category: Optional[str] = Query(None),
    severity: Optional[int] = Query(None, ge=1, le=4),
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
        category=category,
        severity=severity,
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
