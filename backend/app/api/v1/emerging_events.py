"""
SkyPulse Emerging Weather Events API Endpoints
==============================================
REST API for inspecting, filtering, and querying early emerging weather signals,
spatiotemporal convergence clusters, and emergence factor decompositions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.dependencies import get_optional_current_user
from app.models.user import User
from app.schemas.emerging import (
    EmergingEventResponse,
    EmergingEventListResponse,
    EmergingEventSignalsResponse,
    EmergingEventTimelineResponse,
    EmergingEventEvidenceResponse,
)
from app.services.emerging_event_service import emerging_event_service

router = APIRouter(prefix="/emerging-events", tags=["Emerging Weather Events"])


@router.get("", response_model=EmergingEventListResponse)
async def list_emerging_events(
    category: Optional[str] = Query(None, description="Filter by weather category (e.g. RAINFALL, THUNDERSTORM)"),
    state: Optional[str] = Query(None, description="Filter by state (e.g. West Bengal)"),
    min_emergence_score: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum emergence score [0..1]"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence score [0..1]"),
    lookback_minutes: int = Query(120, ge=15, le=1440, description="Lookback window in minutes"),
    start_time: Optional[datetime] = Query(None, description="Filter start timestamp (UTC)"),
    end_time: Optional[datetime] = Query(None, description="Filter end timestamp (UTC)"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Retrieve active emerging weather event clusters across India based on
    spatiotemporal signal convergence.
    """
    try:
        events = await emerging_event_service.detect_emerging_events(
            db=db,
            lookback_minutes=lookback_minutes,
            category=category,
            state=state,
            min_emergence_score=min_emergence_score,
            min_confidence=min_confidence,
            start_time=start_time,
            end_time=end_time,
        )

        active_count = sum(1 for e in events if e.state.value in {"SIGNAL", "DEVELOPING", "EMERGING", "CONFIRMED"})

        return EmergingEventListResponse(
            total=len(events),
            active_count=active_count,
            items=events,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "EMERGING_DETECTION_ERROR",
                "message": f"Failed to execute emerging event detection: {str(exc)}",
                "details": {},
            },
        )


@router.get("/{emerging_id}", response_model=EmergingEventResponse)
async def get_emerging_event(
    emerging_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Retrieve full spatiotemporal details and 9-factor decomposition for a specific emerging event cluster.
    """
    event = await emerging_event_service.get_emerging_event_by_id(db=db, emerging_id=emerging_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EMERGING_EVENT_NOT_FOUND",
                "message": f"Emerging weather event cluster '{emerging_id}' not found or expired.",
                "details": {"emerging_id": emerging_id},
            },
        )
    return event


@router.get("/{emerging_id}/signals", response_model=EmergingEventSignalsResponse)
async def get_emerging_event_signals(
    emerging_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Retrieve the constituent signal reports feeding this emerging cluster.
    """
    event = await emerging_event_service.get_emerging_event_by_id(db=db, emerging_id=emerging_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EMERGING_EVENT_NOT_FOUND",
                "message": f"Emerging weather event cluster '{emerging_id}' not found.",
                "details": {"emerging_id": emerging_id},
            },
        )

    return EmergingEventSignalsResponse(
        emerging_event_id=event.id,
        total_signals=len(event.signals),
        dominant_category=event.dominant_category.value,
        signals=event.signals,
    )


@router.get("/{emerging_id}/timeline", response_model=EmergingEventTimelineResponse)
async def get_emerging_event_timeline(
    emerging_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Retrieve chronological state transition milestones for the emerging cluster.
    """
    event = await emerging_event_service.get_emerging_event_by_id(db=db, emerging_id=emerging_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EMERGING_EVENT_NOT_FOUND",
                "message": f"Emerging weather event cluster '{emerging_id}' not found.",
                "details": {"emerging_id": emerging_id},
            },
        )

    return EmergingEventTimelineResponse(
        emerging_event_id=event.id,
        state=event.state,
        milestones=event.timeline,
    )


@router.get("/{emerging_id}/evidence", response_model=EmergingEventEvidenceResponse)
async def get_emerging_event_evidence(
    emerging_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Retrieve evidence breakdown, source distribution, and 9-factor emergence decomposition.
    """
    event = await emerging_event_service.get_emerging_event_by_id(db=db, emerging_id=emerging_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EMERGING_EVENT_NOT_FOUND",
                "message": f"Emerging weather event cluster '{emerging_id}' not found.",
                "details": {"emerging_id": emerging_id},
            },
        )

    source_div: Dict[str, int] = {}
    for sig in event.signals:
        source_div[sig.source_type] = source_div.get(sig.source_type, 0) + 1

    supporting = sum(1 for s in event.signals if not s.is_contradictory)
    contradicting = sum(1 for s in event.signals if s.is_contradictory)

    return EmergingEventEvidenceResponse(
        emerging_event_id=event.id,
        emergence_score=event.emergence_score,
        confidence_score=event.confidence_score,
        source_diversity=source_div,
        supporting_signals_count=supporting,
        contradicting_signals_count=contradicting,
        factors=event.factors,
    )
