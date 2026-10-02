"""
SkyPulse DWEG (Dynamic Weather Evidence Graph) API Endpoints — Phase 10
========================================================================
Implements graph queries, confidence field GeoJSON, propagation timeline,
evidence chain reconstruction, and real-time propagation alerts.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.weather_event import WeatherEvent
from app.services.dweg_service import dweg_service
from app.schemas.dweg import (
    DWEGGraphResponse,
    ConfidenceFieldResponse,
    PropagationTimelineResponse,
    EvidenceChainResponse,
    PropagationAlertsResponse,
)

router = APIRouter(prefix="/dweg", tags=["Dynamic Weather Evidence Graph (DWEG)"])


def _parse_uuid(event_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_UUID", "message": f"'{event_id}' is not a valid UUID"},
        )


async def _verify_event_exists(event_id: str, db: AsyncSession) -> WeatherEvent:
    e_uuid = _parse_uuid(event_id)
    res = await db.execute(select(WeatherEvent).where(WeatherEvent.id == e_uuid))
    event = res.scalars().first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "EVENT_NOT_FOUND", "message": f"Weather event {event_id} not found"},
        )
    return event


# -----------------------------------------------------------------------------
# Graph Endpoints: /{event_id}/graph & /events/{event_id}/graph
# -----------------------------------------------------------------------------
@router.get("/{event_id}/graph", response_model=DWEGGraphResponse)
@router.get("/events/{event_id}/graph", response_model=DWEGGraphResponse)
async def get_dweg_graph(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the full Dynamic Weather Evidence Graph representation for an event."""
    await _verify_event_exists(event_id, db)
    return await dweg_service.build_event_graph(event_id, db)


# -----------------------------------------------------------------------------
# Confidence Field Endpoints: /{event_id}/confidence-field & /events/{event_id}/confidence-field
# -----------------------------------------------------------------------------
@router.get("/{event_id}/confidence-field", response_model=ConfidenceFieldResponse)
@router.get("/events/{event_id}/confidence-field", response_model=ConfidenceFieldResponse)
async def get_confidence_field(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns GeoJSON FeatureCollection with point features weighted by evidence density
    and source corroboration, suitable for MapLibre/Leaflet heatmap layers.
    """
    await _verify_event_exists(event_id, db)
    return await dweg_service.compute_confidence_field(event_id, db)


# -----------------------------------------------------------------------------
# Propagation Timeline Endpoints: /{event_id}/propagation-timeline & /{event_id}/propagation
# -----------------------------------------------------------------------------
@router.get("/{event_id}/propagation-timeline", response_model=PropagationTimelineResponse)
@router.get("/{event_id}/propagation", response_model=PropagationTimelineResponse)
@router.get("/events/{event_id}/propagation-timeline", response_model=PropagationTimelineResponse)
async def get_propagation_timeline(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Track the cross-district spatio-temporal propagation path of a weather phenomenon."""
    await _verify_event_exists(event_id, db)
    return await dweg_service.get_propagation_timeline(event_id, db)


# -----------------------------------------------------------------------------
# Evidence Chain Endpoints: /{event_id}/evidence-chain & /{event_id}/chain
# -----------------------------------------------------------------------------
@router.get("/{event_id}/evidence-chain", response_model=EvidenceChainResponse)
@router.get("/{event_id}/chain", response_model=EvidenceChainResponse)
@router.get("/events/{event_id}/evidence-chain", response_model=EvidenceChainResponse)
async def get_evidence_chain(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Explainable multi-source evidence provenance chain and narrative leading to event verification."""
    await _verify_event_exists(event_id, db)
    return await dweg_service.generate_evidence_chain(event_id, db)


# -----------------------------------------------------------------------------
# Propagation Alerts: /propagation-alerts & /alerts
# -----------------------------------------------------------------------------
@router.get("/propagation-alerts", response_model=PropagationAlertsResponse)
@router.get("/alerts", response_model=PropagationAlertsResponse)
async def get_propagation_alerts(
    db: AsyncSession = Depends(get_db),
):
    """Get active spatial propagation alerts across adjacent administrative districts."""
    return await dweg_service.get_propagation_alerts(db)
