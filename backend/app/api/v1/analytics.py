from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.analytics import (
    NationalAnalytics,
    StateAnalytics,
    TimeseriesResponse,
)
from app.services.analytics_service import (
    get_national_analytics,
    get_state_analytics,
    get_timeseries_analytics,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/national", response_model=NationalAnalytics)
async def national_analytics(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated national overview: total events, category breakdown, verification, severity, and top states."""
    return await get_national_analytics(
        db=db,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/state/{state}", response_model=StateAnalytics)
async def state_analytics(
    state: str,
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """State-level breakdown including active events, categories, and top affected districts."""
    return await get_state_analytics(
        db=db,
        state=state,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/timeseries", response_model=TimeseriesResponse)
async def timeseries_analytics(
    metric: str = Query("events", pattern="^(events|reports)$"),
    interval: str = Query("hourly", pattern="^(hourly|daily)$"),
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Historical timeseries data for event and report frequencies."""
    return await get_timeseries_analytics(
        db=db,
        metric=metric,
        interval=interval,
        days=days,
    )
