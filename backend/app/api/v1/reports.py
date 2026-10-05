import logging
import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.dependencies import get_optional_current_user
from app.core.rate_limit import rate_limiter
from app.core.audit import log_audit_event
from app.models.user import User
from app.models.media import Media
from app.models.weather_report import WeatherReport
from app.models.enums import AuditActionType, UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.report import (
    CreateReportRequest,
    CreateReportResponse,
    ReportSummary,
    ReportDetail,
)
from app.schemas.storage import (
    MediaDetailResponse,
    AttachMediaRequest,
)
from app.services.report_service import (
    create_report,
    list_reports,
    get_report_by_id,
)
from app.services.storage_service import storage_service

logger = logging.getLogger("skypulse.api.reports")

router = APIRouter(prefix="/reports", tags=["Weather Reports"])


@router.post(
    "",
    response_model=CreateReportResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter(requests_per_minute=30))],
)
async def submit_weather_report(
    data: CreateReportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Submit a citizen or observational weather report.
    Enforces geographic bounds (India), validates categories, and issues an SP- tracking ID.
    """
    response = await create_report(db=db, data=data, user=user)

    await log_audit_event(
        db=db,
        action_type=AuditActionType.CREATE.value,
        entity_type="WeatherReport",
        entity_id=uuid.UUID(response.id),
        user_id=user.id if user else None,
        new_value={"tracking_id": response.tracking_id, "category": data.event_type},
        request=request,
    )
    await db.commit()

    # Stream citizen raw observation to common Kafka/Redpanda topic
    try:
        from connectors.schema import CanonicalRawEvent
        from connectors.kafka_bus import kafka_producer, TOPIC_RAW

        raw_event = CanonicalRawEvent(
            ingestion_id=response.id,
            source_id="citizen-reports",
            source_type="CITIZEN",
            external_id=response.tracking_id,
            text=data.description,
            latitude=data.latitude,
            longitude=data.longitude,
            city=data.location_name,
            suggested_category=data.event_type,
            severity=data.severity,
            raw_payload={"location_name": data.location_name, "media_ids": data.media_ids},
            is_demo=False,
        )
        await kafka_producer.publish(TOPIC_RAW, raw_event, key=response.id)
    except Exception as e:
        # Non-fatal if broker offline
        pass

    return response


@router.get("", response_model=PaginatedResponse[ReportSummary])
async def get_weather_reports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    severity: Optional[int] = Query(None, ge=1, le=4),
    status: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List paginated weather reports with multiple filtering dimensions."""
    reports, total = await list_reports(
        db=db,
        page=page,
        per_page=per_page,
        category=category,
        severity=severity,
        status=status,
        state=state,
        district=district,
        source_id=source_id,
        from_date=from_date,
        to_date=to_date,
    )
    return PaginatedResponse.build(items=reports, total=total, page=page, per_page=per_page)


@router.get("/search")
async def search_weather_reports(
    q: Optional[str] = Query(None, description="Full-text query string"),
    category: Optional[str] = Query(None, description="Primary event category"),
    city: Optional[str] = Query(None, description="City name"),
    state: Optional[str] = Query(None, description="State name"),
    verification_status: Optional[str] = Query(None, description="Verification status"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence score"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of hits to return"),
):
    """
    Search weather reports using full-text keyword indexing and faceted filters in OpenSearch.
    Falls back seamlessly to in-memory/structured search if OpenSearch is offline.
    """
    from ai.opensearch_indexer import opensearch_indexer
    results = await opensearch_indexer.search_reports(
        category=category,
        city=city,
        state=state,
        verification_status=verification_status,
        min_confidence=min_confidence,
        query_text=q,
        limit=limit,
    )
    return {
        "status": "SUCCESS",
        "search_engine": "OPENSEARCH" if opensearch_indexer.is_live else "FALLBACK",
        "total_hits": len(results),
        "hits": results,
    }


@router.get("/{report_id}", response_model=ReportDetail)
async def get_single_weather_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full details of a specific weather report by UUID."""
    try:
        r_uuid = uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_UUID",
                "message": "Provided report ID is not a valid UUID",
                "details": {"report_id": report_id},
            },
        )

    report = await get_report_by_id(db=db, report_id=r_uuid)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "REPORT_NOT_FOUND",
                "message": f"Weather report with ID {report_id} was not found",
                "details": {"report_id": report_id},
            },
        )
    return report


@router.get("/{report_id}/media", response_model=List[MediaDetailResponse])
async def get_report_media_list(
    report_id: str,
    user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all media and evidence items attached to a specific weather report.
    Returns signed URLs for secure private viewing.
    """
    try:
        r_uuid = uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_UUID", "message": "Invalid report UUID format."},
        )

    # Verify report exists
    report_obj = await db.scalar(select(WeatherReport).where(WeatherReport.id == r_uuid))
    if not report_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "REPORT_NOT_FOUND", "message": f"Report '{report_id}' not found."},
        )

    # RBAC check: citizen owner or analyst/admin/government
    if user and user.role == UserRole.CITIZEN.value:
        if report_obj.submitted_by and report_obj.submitted_by != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "You are not authorized to view media for this report."},
            )

    media_records = (
        await db.scalars(
            select(Media).where(
                Media.weather_report_id == r_uuid,
                Media.upload_status != "DELETED",
            )
        )
    ).all()

    results = []
    for m in media_records:
        url, thumb_url = await storage_service.get_media_access_url(m)
        results.append(
            MediaDetailResponse(
                id=str(m.id),
                weather_report_id=str(m.weather_report_id) if m.weather_report_id else None,
                citizen_id=str(m.citizen_id) if m.citizen_id else None,
                event_id=str(m.event_id) if m.event_id else None,
                evidence_id=str(m.evidence_id) if m.evidence_id else None,
                media_type=m.media_type,
                storage_provider=m.storage_provider,
                storage_key=m.storage_key,
                storage_path=m.storage_path,
                storage_bucket=m.storage_bucket,
                original_filename=m.original_filename,
                safe_filename=m.safe_filename,
                file_size_bytes=m.file_size_bytes,
                mime_type=m.mime_type,
                content_hash=m.content_hash,
                upload_status=m.upload_status,
                url=url,
                thumbnail_url=thumb_url,
                uploaded_at=m.uploaded_at,
            )
        )
    return results


@router.post("/{report_id}/media")
async def attach_media_to_report(
    report_id: str,
    payload: AttachMediaRequest,
    user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Attach pre-uploaded media items to an existing weather report.
    """
    try:
        r_uuid = uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_UUID", "message": "Invalid report UUID format."},
        )

    report_obj = await db.scalar(select(WeatherReport).where(WeatherReport.id == r_uuid))
    if not report_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "REPORT_NOT_FOUND", "message": f"Report '{report_id}' not found."},
        )

    attached_count = 0
    for mid in payload.media_ids:
        try:
            m_uuid = uuid.UUID(mid)
            media_item = await db.scalar(select(Media).where(Media.id == m_uuid))
            if media_item:
                media_item.weather_report_id = r_uuid
                if report_obj.submitted_by:
                    media_item.citizen_id = report_obj.submitted_by
                attached_count += 1
        except Exception as e:
            logger.warning("Failed attaching media %s: %s", mid, e)

    await db.commit()
    return {
        "status": "SUCCESS",
        "report_id": report_id,
        "attached_count": attached_count,
        "message": f"Successfully attached {attached_count} media items to report.",
    }

