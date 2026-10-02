import uuid
import random
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any

logger = logging.getLogger("skypulse.report_service")
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload
from geoalchemy2.elements import WKTElement

from app.models.weather_report import WeatherReport
from app.models.source import Source
from app.models.user import User
from app.models.media import Media
from app.models.enums import SourceType, ReportStatus, WeatherCategory
from app.schemas.report import (
    CreateReportRequest,
    CreateReportResponse,
    ReportSummary,
    ReportDetail,
    SourceSummary,
    MediaSummary,
)
from app.schemas.common import LocationSchema


async def get_or_create_citizen_source(db: AsyncSession) -> Source:
    result = await db.execute(
        select(Source).where(Source.source_type == SourceType.CITIZEN.value)
    )
    source = result.scalars().first()
    if not source:
        source = Source(
            name="Citizen Reports",
            description="Crowdsourced weather reports from verified citizens and general public",
            source_type=SourceType.CITIZEN.value,
            connector_class="CitizenConnector",
            config={},
            trust_score=0.5,
            is_active=True,
            is_demo=False,
        )
        db.add(source)
        await db.flush()
    return source


def _build_location_schema(report: WeatherReport) -> LocationSchema:
    return LocationSchema(
        city=report.location_city,
        district=report.location_district,
        state=report.location_state,
        lat=report.location_lat,
        lon=report.location_lon,
        confidence=report.location_confidence,
    )


def _build_source_summary(source: Optional[Source]) -> Optional[SourceSummary]:
    if not source:
        return None
    return SourceSummary(
        id=str(source.id),
        name=source.name,
        type=source.source_type,
        trust_score=source.trust_score,
    )


async def create_report(
    db: AsyncSession,
    data: CreateReportRequest,
    user: Optional[User] = None,
) -> CreateReportResponse:
    source = await get_or_create_citizen_source(db)

    year = datetime.now(timezone.utc).year
    rand_seq = random.randint(100000, 999999)
    tracking_id = f"SP-{year}-{rand_seq}"

    point_geom = None
    if data.latitude is not None and data.longitude is not None:
        point_geom = WKTElement(f"POINT({data.longitude} {data.latitude})", srid=4326)

    event_time = data.event_time or datetime.now(timezone.utc)
    metadata_payload = {
        "tracking_id": tracking_id,
        "location_name": data.location_name,
    }

    report = WeatherReport(
        source_id=source.id,
        submitted_by=user.id if user else None,
        raw_content=data.description,
        normalized_text=data.description,
        primary_category=data.event_type.upper(),
        severity=data.severity or 2,
        classification_confidence=0.75,
        classification_method="RULE_BASED",
        location_point=point_geom,
        location_lat=data.latitude,
        location_lon=data.longitude,
        location_city=data.location_name,
        location_raw=data.location_name,
        location_confidence="MEDIUM" if data.latitude else "LOW",
        event_time=event_time,
        status=ReportStatus.PENDING.value,
        metadata_=metadata_payload,
    )
    db.add(report)
    await db.flush()

    # Link media items if provided
    if data.media_ids:
        for mid in data.media_ids:
            try:
                m_uuid = uuid.UUID(mid)
                m_res = await db.execute(select(Media).where(Media.id == m_uuid))
                media_item = m_res.scalars().first()
                if media_item:
                    media_item.weather_report_id = report.id
            except ValueError:
                pass
        await db.flush()

    # Process report through Unified AI Pipeline & DWEG
    try:
        from app.services.unified_ingestion_service import unified_ingestion_pipeline
        await unified_ingestion_pipeline.process_report_ai(report=report, db=db)
    except Exception as pipe_err:
        logger.warning("Citizen report AI pipeline non-fatal exception: %s", pipe_err)

    await db.commit()

    return CreateReportResponse(
        id=str(report.id),
        status=ReportStatus.PENDING.value,
        tracking_id=tracking_id,
        message="Weather report submitted successfully. It will be reviewed by our AI pipeline and verification team.",
        submitted_at=report.ingested_at,
    )


async def list_reports(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
    category: Optional[str] = None,
    severity: Optional[int] = None,
    status: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    source_id: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> Tuple[List[ReportSummary], int]:
    query = (
        select(WeatherReport)
        .options(selectinload(WeatherReport.source), selectinload(WeatherReport.media_items))
        .where(WeatherReport.is_deleted == False)
    )

    filters = []
    if category:
        filters.append(WeatherReport.primary_category == category.upper())
    if severity is not None:
        filters.append(WeatherReport.severity == severity)
    if status:
        filters.append(WeatherReport.status == status.upper())
    if state:
        filters.append(WeatherReport.location_state.ilike(f"%{state}%"))
    if district:
        filters.append(WeatherReport.location_district.ilike(f"%{district}%"))
    if source_id:
        try:
            filters.append(WeatherReport.source_id == uuid.UUID(source_id))
        except ValueError:
            pass
    if from_date:
        filters.append(WeatherReport.event_time >= from_date)
    if to_date:
        filters.append(WeatherReport.event_time <= to_date)

    if filters:
        query = query.where(and_(*filters))

    # Count total
    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.order_by(desc(WeatherReport.ingested_at)).offset(offset).limit(per_page)
    result = await db.execute(query)
    reports = result.scalars().all()

    summaries = [
        ReportSummary(
            id=str(r.id),
            primary_category=r.primary_category,
            sub_category=r.sub_category,
            severity=r.severity,
            confidence_score=r.classification_confidence,
            classification_confidence=r.classification_confidence,
            location=_build_location_schema(r),
            event_time=r.event_time,
            ingested_at=r.ingested_at,
            canonical_event_id=str(r.canonical_event_id) if r.canonical_event_id else None,
            verification_status="UNVERIFIED",
            source=_build_source_summary(r.source),
            media_count=len(r.media_items),
            is_demo=r.is_demo,
        )
        for r in reports
    ]
    return summaries, total


async def get_report_by_id(db: AsyncSession, report_id: uuid.UUID) -> Optional[ReportDetail]:
    query = (
        select(WeatherReport)
        .options(selectinload(WeatherReport.source), selectinload(WeatherReport.media_items))
        .where(WeatherReport.id == report_id, WeatherReport.is_deleted == False)
    )
    result = await db.execute(query)
    report = result.scalars().first()
    if not report:
        return None

    media_summaries = [
        MediaSummary(
            id=str(m.id),
            media_type=m.media_type,
            url=m.storage_path or "",
            thumbnail_url=m.thumbnail_path,
        )
        for m in report.media_items
    ]

    return ReportDetail(
        id=str(report.id),
        normalized_text=report.normalized_text or report.raw_content,
        primary_category=report.primary_category,
        sub_category=report.sub_category,
        severity=report.severity,
        classification_confidence=report.classification_confidence,
        classification_method=report.classification_method,
        location=_build_location_schema(report),
        event_time=report.event_time,
        ingested_at=report.ingested_at,
        canonical_event_id=str(report.canonical_event_id) if report.canonical_event_id else None,
        is_duplicate=report.is_duplicate,
        ai_extraction=report.ai_extraction,
        source=_build_source_summary(report.source),
        media=media_summaries,
        verification_status="UNVERIFIED",
        is_demo=report.is_demo,
    )
