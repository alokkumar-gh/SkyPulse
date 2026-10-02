from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.schemas.analytics import (
    NationalAnalytics,
    StateAnalytics,
    StatePeriod,
    TimeseriesResponse,
    TimeseriesPoint,
)


async def get_national_analytics(
    db: AsyncSession,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> NationalAnalytics:
    now = datetime.now(timezone.utc)
    if not from_date:
        from_date = now - timedelta(days=7)
    if not to_date:
        to_date = now

    event_filter = and_(
        WeatherEvent.is_deleted == False,
        WeatherEvent.first_reported_at >= from_date,
        WeatherEvent.first_reported_at <= to_date,
    )

    # 1. Total events
    total_events_res = await db.execute(
        select(func.count()).select_from(WeatherEvent).where(event_filter)
    )
    total_events = total_events_res.scalar() or 0

    # 2. Active events
    active_events_res = await db.execute(
        select(func.count())
        .select_from(WeatherEvent)
        .where(event_filter, WeatherEvent.is_active == True)
    )
    active_events = active_events_res.scalar() or 0

    # 3. Total reports
    report_filter = and_(
        WeatherReport.is_deleted == False,
        WeatherReport.ingested_at >= from_date,
        WeatherReport.ingested_at <= to_date,
    )
    total_reports_res = await db.execute(
        select(func.count()).select_from(WeatherReport).where(report_filter)
    )
    total_reports = total_reports_res.scalar() or 0

    # 4. By category
    cat_res = await db.execute(
        select(WeatherEvent.category, func.count())
        .where(event_filter)
        .group_by(WeatherEvent.category)
    )
    by_category = {row[0]: row[1] for row in cat_res.all()}

    # 5. By verification status
    status_res = await db.execute(
        select(WeatherEvent.verification_status, func.count())
        .where(event_filter)
        .group_by(WeatherEvent.verification_status)
    )
    by_verification_status = {row[0]: row[1] for row in status_res.all()}

    # 6. By severity
    sev_res = await db.execute(
        select(WeatherEvent.severity, func.count())
        .where(event_filter)
        .group_by(WeatherEvent.severity)
    )
    by_severity = {str(row[0]): row[1] for row in sev_res.all()}

    # 7. Anomalous events
    anom_res = await db.execute(
        select(func.count())
        .select_from(WeatherEvent)
        .where(event_filter, WeatherEvent.is_anomalous == True)
    )
    anomalous_events = anom_res.scalar() or 0

    # 8. Top states
    states_res = await db.execute(
        select(WeatherEvent.primary_state, func.count().label("cnt"))
        .where(event_filter, WeatherEvent.primary_state.isnot(None))
        .group_by(WeatherEvent.primary_state)
        .order_by(desc("cnt"))
        .limit(10)
    )
    top_states = [
        StatePeriod(state=row[0], event_count=row[1]) for row in states_res.all() if row[0]
    ]

    return NationalAnalytics(
        period={"from": from_date.isoformat(), "to": to_date.isoformat()},
        total_events=total_events,
        active_events=active_events,
        total_reports=total_reports,
        by_category=by_category,
        by_verification_status=by_verification_status,
        by_severity=by_severity,
        anomalous_events=anomalous_events,
        top_states=top_states,
    )


async def get_state_analytics(
    db: AsyncSession,
    state: str,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> StateAnalytics:
    now = datetime.now(timezone.utc)
    if not from_date:
        from_date = now - timedelta(days=7)
    if not to_date:
        to_date = now

    event_filter = and_(
        WeatherEvent.is_deleted == False,
        WeatherEvent.primary_state.ilike(f"%{state}%"),
        WeatherEvent.first_reported_at >= from_date,
        WeatherEvent.first_reported_at <= to_date,
    )

    total_events_res = await db.execute(
        select(func.count()).select_from(WeatherEvent).where(event_filter)
    )
    total_events = total_events_res.scalar() or 0

    active_events_res = await db.execute(
        select(func.count())
        .select_from(WeatherEvent)
        .where(event_filter, WeatherEvent.is_active == True)
    )
    active_events = active_events_res.scalar() or 0

    report_filter = and_(
        WeatherReport.is_deleted == False,
        WeatherReport.location_state.ilike(f"%{state}%"),
        WeatherReport.ingested_at >= from_date,
        WeatherReport.ingested_at <= to_date,
    )
    total_reports_res = await db.execute(
        select(func.count()).select_from(WeatherReport).where(report_filter)
    )
    total_reports = total_reports_res.scalar() or 0

    cat_res = await db.execute(
        select(WeatherEvent.category, func.count())
        .where(event_filter)
        .group_by(WeatherEvent.category)
    )
    by_category = {row[0]: row[1] for row in cat_res.all()}

    status_res = await db.execute(
        select(WeatherEvent.verification_status, func.count())
        .where(event_filter)
        .group_by(WeatherEvent.verification_status)
    )
    by_verification_status = {row[0]: row[1] for row in status_res.all()}

    sev_res = await db.execute(
        select(WeatherEvent.severity, func.count())
        .where(event_filter)
        .group_by(WeatherEvent.severity)
    )
    by_severity = {str(row[0]): row[1] for row in sev_res.all()}

    dist_res = await db.execute(
        select(WeatherEvent.primary_district, func.count().label("cnt"))
        .where(event_filter, WeatherEvent.primary_district.isnot(None))
        .group_by(WeatherEvent.primary_district)
        .order_by(desc("cnt"))
        .limit(10)
    )
    top_districts = [
        {"district": row[0], "event_count": row[1]} for row in dist_res.all() if row[0]
    ]

    return StateAnalytics(
        state=state,
        period={"from": from_date.isoformat(), "to": to_date.isoformat()},
        total_events=total_events,
        active_events=active_events,
        total_reports=total_reports,
        by_category=by_category,
        by_verification_status=by_verification_status,
        by_severity=by_severity,
        top_districts=top_districts,
    )


async def get_timeseries_analytics(
    db: AsyncSession,
    metric: str = "events",
    interval: str = "hourly",
    days: int = 7,
) -> TimeseriesResponse:
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days)

    series: List[TimeseriesPoint] = []
    # Build stepped intervals
    step_hours = 1 if interval == "hourly" else 24
    current_bucket = start_time

    while current_bucket <= now:
        next_bucket = current_bucket + timedelta(hours=step_hours)
        if metric == "reports":
            cnt_res = await db.execute(
                select(func.count())
                .select_from(WeatherReport)
                .where(
                    WeatherReport.is_deleted == False,
                    WeatherReport.ingested_at >= current_bucket,
                    WeatherReport.ingested_at < next_bucket,
                )
            )
        else:
            cnt_res = await db.execute(
                select(func.count())
                .select_from(WeatherEvent)
                .where(
                    WeatherEvent.is_deleted == False,
                    WeatherEvent.first_reported_at >= current_bucket,
                    WeatherEvent.first_reported_at < next_bucket,
                )
            )
        count = float(cnt_res.scalar() or 0)
        series.append(TimeseriesPoint(timestamp=current_bucket, value=count))
        current_bucket = next_bucket

    return TimeseriesResponse(
        metric=metric,
        interval=interval,
        series=series,
    )
