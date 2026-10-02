import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.dependencies import require_role
from app.core.audit import log_audit_event
from app.models.user import User
from app.models.enums import UserRole, AuditActionType
from app.schemas.common import PaginatedResponse
from app.schemas.verification import (
    VerificationResult,
    VerificationQueueItem,
    ManualOverrideRequest,
)
from app.services.verification_service import (
    get_verification_queue,
    get_verification_for_event,
    apply_manual_override,
)

from app.models.duplicate_cluster import DuplicateCluster
from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.schemas.admin import (
    DuplicateClusterResponse,
    ClusterReportItem,
    SplitClusterRequest,
    MergeClustersRequest,
)

router = APIRouter(prefix="/verification", tags=["Verification"])


@router.get(
    "/clusters",
    response_model=list[DuplicateClusterResponse],
    dependencies=[Depends(require_role(UserRole.ANALYST, UserRole.ADMIN, UserRole.GOVERNMENT))],
)
async def get_clusters(
    limit: int = Query(50, ge=1, le=200),
    event_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve duplicate event clusters for analyst inspection."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    query = (
        select(DuplicateCluster)
        .options(selectinload(DuplicateCluster.canonical_event))
        .order_by(DuplicateCluster.created_at.desc())
    )
    if event_id:
        try:
            e_uuid = uuid.UUID(event_id)
            query = query.where(DuplicateCluster.canonical_event_id == e_uuid)
        except ValueError:
            pass

    query = query.limit(limit)
    res = await db.execute(query)
    clusters = res.scalars().all()

    responses = []
    for c in clusters:
        reports_list: list[ClusterReportItem] = []
        if c.canonical_event_id:
            rep_res = await db.execute(
                select(WeatherReport).where(WeatherReport.canonical_event_id == c.canonical_event_id)
            )
            for rep in rep_res.scalars().all():
                reports_list.append(
                    ClusterReportItem(
                        id=str(rep.id),
                        category=rep.primary_category,
                        severity=rep.severity,
                        source_type=rep.primary_category,
                        event_time=rep.event_time,
                        location_state=rep.location_state,
                        location_district=rep.location_district,
                        normalized_text=rep.normalized_text or rep.raw_content,
                        is_duplicate=rep.is_duplicate,
                    )
                )

        responses.append(
            DuplicateClusterResponse(
                id=str(c.id),
                canonical_event_id=str(c.canonical_event_id) if c.canonical_event_id else None,
                member_count=len(reports_list) if reports_list else c.member_count,
                state=c.canonical_event.primary_state if c.canonical_event else None,
                created_at=c.created_at,
                reports=reports_list,
            )
        )

    return responses


@router.post(
    "/clusters/split",
    dependencies=[Depends(require_role(UserRole.ANALYST, UserRole.ADMIN))],
)
async def split_duplicate_cluster(
    data: SplitClusterRequest,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ANALYST, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Analyst operation: Manually decouple mismatched reports from a duplicate cluster."""
    from sqlalchemy import select
    for rid_str in data.report_ids_to_remove:
        try:
            rid = uuid.UUID(rid_str)
            r_res = await db.execute(select(WeatherReport).where(WeatherReport.id == rid))
            rep = r_res.scalars().first()
            if rep:
                rep.canonical_event_id = None
                rep.is_duplicate = False
        except ValueError:
            pass

    await log_audit_event(
        db=db,
        action_type=AuditActionType.SPLIT_CLUSTER.value,
        entity_type="DuplicateCluster",
        user_id=current_user.id,
        new_value={"removed_report_ids": data.report_ids_to_remove, "reason": data.reason},
        request=request,
    )
    await db.commit()
    return {"message": "Cluster successfully split", "removed_count": len(data.report_ids_to_remove)}


@router.post(
    "/clusters/merge",
    dependencies=[Depends(require_role(UserRole.ANALYST, UserRole.ADMIN))],
)
async def merge_duplicate_clusters(
    data: MergeClustersRequest,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ANALYST, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Analyst operation: Merge two canonical events and their constituent report clusters."""
    from sqlalchemy import select
    try:
        p_id = uuid.UUID(data.primary_event_id)
        s_id = uuid.UUID(data.secondary_event_id)
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": "INVALID_UUID", "message": "Invalid event UUID"})

    p_res = await db.execute(select(WeatherEvent).where(WeatherEvent.id == p_id))
    s_res = await db.execute(select(WeatherEvent).where(WeatherEvent.id == s_id))
    primary = p_res.scalars().first()
    secondary = s_res.scalars().first()

    if not primary or not secondary:
        raise HTTPException(status_code=404, detail={"error": "EVENT_NOT_FOUND", "message": "Event not found"})

    secondary.is_active = False

    rep_res = await db.execute(select(WeatherReport).where(WeatherReport.canonical_event_id == s_id))
    for rep in rep_res.scalars().all():
        rep.canonical_event_id = p_id
        primary.evidence_count += 1

    await log_audit_event(
        db=db,
        action_type=AuditActionType.MERGE_CLUSTER.value,
        entity_type="WeatherEvent",
        entity_id=p_id,
        user_id=current_user.id,
        new_value={"secondary_event_id": str(s_id), "reason": data.reason},
        request=request,
    )
    await db.commit()
    return {"message": "Clusters successfully merged", "primary_event_id": str(p_id)}



@router.get(
    "/queue",
    response_model=PaginatedResponse[VerificationQueueItem],
    dependencies=[Depends(require_role(UserRole.ANALYST, UserRole.ADMIN, UserRole.GOVERNMENT))],
)
async def get_queue(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    severity: Optional[int] = Query(None, ge=1, le=4),
    db: AsyncSession = Depends(get_db),
):
    """Analyst verification queue for flagged, unverified, or anomalous weather events."""
    items, total = await get_verification_queue(
        db=db,
        page=page,
        per_page=per_page,
        status=status_filter,
        state=state,
        district=district,
        category=category,
        severity=severity,
    )
    return PaginatedResponse.build(items=items, total=total, page=page, per_page=per_page)


@router.get("/{event_id}", response_model=VerificationResult)
async def get_verification_result(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the multi-signal AI verification score and evidence items for an event."""
    try:
        e_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_UUID",
                "message": "Provided event ID is not a valid UUID",
                "details": {"event_id": event_id},
            },
        )

    result = await get_verification_for_event(db=db, event_id=e_uuid)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EVENT_NOT_FOUND",
                "message": f"Weather event with ID {event_id} was not found",
                "details": {"event_id": event_id},
            },
        )
    return result


@router.post(
    "/{event_id}/override",
    response_model=VerificationResult,
    dependencies=[Depends(require_role(UserRole.ANALYST, UserRole.ADMIN))],
)
async def override_verification(
    event_id: str,
    data: ManualOverrideRequest,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ANALYST, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Apply an authorized manual override to an event's verification status with mandatory justification."""
    try:
        data.validate_status()
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_STATUS",
                "message": str(ve),
                "details": {"status": data.status},
            },
        )

    try:
        e_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_UUID",
                "message": "Provided event ID is not a valid UUID",
                "details": {"event_id": event_id},
            },
        )

    try:
        updated_vr = await apply_manual_override(
            db=db,
            event_id=e_uuid,
            user_id=current_user.id,
            data=data,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "EVENT_NOT_FOUND",
                "message": f"Weather event with ID {event_id} was not found",
                "details": {"event_id": event_id},
            },
        )

    await log_audit_event(
        db=db,
        action_type=AuditActionType.VERIFY.value,
        entity_type="VerificationResult",
        entity_id=e_uuid,
        user_id=current_user.id,
        new_value={"status": data.status, "reason": data.reason},
        request=request,
    )
    await db.commit()

    # Phase 6/9 Real-time WebSocket event broadcast
    try:
        from workers.realtime_gateway import realtime_gateway
        await realtime_gateway.broadcast({
            "type": "VERIFICATION_UPDATE",
            "event_id": str(e_uuid),
            "status": data.status,
            "confidence_score": updated_vr.confidence_score,
            "updated_by": str(current_user.id),
        })
    except Exception:
        pass

    return updated_vr


@router.put(
    "/{event_id}",
    response_model=VerificationResult,
    dependencies=[Depends(require_role(UserRole.ANALYST, UserRole.ADMIN))],
)
async def put_override_verification(
    event_id: str,
    data: ManualOverrideRequest,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ANALYST, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """PUT alias for manual verification override to support RESTful PUT conventions."""
    return await override_verification(
        event_id=event_id,
        data=data,
        request=request,
        current_user=current_user,
        db=db,
    )

