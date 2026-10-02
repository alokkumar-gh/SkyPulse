"""
Alerts REST API — SkyPulse Phase 6
GET    /api/v1/alerts
GET    /api/v1/alerts/{id}
POST   /api/v1/alerts/{id}/acknowledge
GET    /api/v1/alerts/stats   (ANALYST+)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.alert import Alert
from app.models.user import User
from app.services.alert_service import alert_engine

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# ── Response schemas ──────────────────────────────────────────────────────
class AlertOut(BaseModel):
    id: uuid.UUID
    event_id: Optional[uuid.UUID]
    alert_type: str
    priority: str
    status: str
    title: str
    message: str
    location_city: Optional[str]
    location_district: Optional[str]
    location_state: Optional[str]
    location_lat: Optional[float]
    location_lon: Optional[float]
    severity: int
    confidence: Optional[float]
    created_at: datetime
    expires_at: Optional[datetime]
    acknowledged_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("", response_model=List[AlertOut])
async def list_alerts(
    priority: Optional[str] = None,
    alert_status: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List recent alerts. Filters by priority, status, state.
    All authenticated users can see alerts.
    """
    q = (
        select(Alert)
        .order_by(desc(Alert.created_at))
        .limit(min(limit, 200))
        .offset(offset)
    )
    if priority:
        q = q.where(Alert.priority == priority.upper())
    if alert_status:
        q = q.where(Alert.status == alert_status.upper())
    if state:
        q = q.where(Alert.location_state == state)

    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalars().first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "error": "NOT_FOUND", "message": "Alert not found", "details": {}
        })
    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark an alert as acknowledged."""
    alert = await alert_engine.acknowledge_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "error": "NOT_FOUND", "message": "Alert not found", "details": {}
        })
    return alert
