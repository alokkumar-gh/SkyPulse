import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.core.dependencies import require_role, get_optional_current_user
from app.core.audit import log_audit_event
from app.models.user import User
from app.models.source import Source, SourceReputationHistory, ConnectorHealth
from app.models.enums import UserRole, AuditActionType, SourceType, ConnectorStatus, ReputationState
from app.schemas.source import (
    SourceResponse,
    TrustHistoryResponse,
    TrustHistoryEntry,
    CreateConnectorRequest,
    UpdateConnectorRequest,
    SourceReputationResponse,
    SourceReputationListResponse,
    SourceReputationTimelineResponse,
    SourceReputationCategoriesResponse,
    SourceReputationEvidenceResponse,
)
from app.services.source_reputation_service import source_reputation_service

router = APIRouter(prefix="/sources", tags=["Data Sources & Connectors"])


def _build_source_response(source: Source) -> SourceResponse:
    health_status = source.health.status if source.health else "UNKNOWN"
    last_success = source.health.last_success_at if source.health else None
    records_hour = source.health.records_ingested_last_hour if source.health else 0

    return SourceResponse(
        id=str(source.id),
        name=source.name,
        source_type=source.source_type,
        trust_score=source.trust_score,
        is_active=source.is_active,
        is_demo=source.is_demo,
        last_success_at=last_success,
        health_status=health_status,
        records_ingested_last_hour=records_hour,
    )


# =========================================================================
# Source Reputation Graph Endpoints (Signature Intelligence)
# =========================================================================

@router.get("/reputation", response_model=SourceReputationListResponse)
async def list_sources_reputation(
    source_type: Optional[str] = Query(None, description="Filter by SourceType"),
    reputation_state: Optional[str] = Query(None, description="Filter by ReputationState"),
    category: Optional[str] = Query(None, description="Filter by WeatherCategory activity"),
    min_observations: Optional[int] = Query(None, description="Minimum non-duplicate observations"),
    min_trust: Optional[float] = Query(None, description="Minimum current trust score (0.0 - 1.0)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    List historical evidence-driven source reputation profiles across registered sources.
    Evaluates corroboration rates, contradiction rates, verification support, and category breakdowns.
    """
    items = await source_reputation_service.list_sources_reputation(
        db=db,
        source_type=source_type,
        reputation_state=reputation_state,
        min_observations=min_observations,
        min_trust=min_trust,
        is_active=is_active,
        category=category,
    )

    # Privacy filter: for unauthenticated or public/citizen users, redact internal citizen IDs
    if not current_user or current_user.role in (UserRole.PUBLIC.value, UserRole.CITIZEN.value):
        for item in items:
            if item.source_type == SourceType.CITIZEN.value:
                item.source_name = f"Citizen Contributor #{item.source_id[:6]}"

    return SourceReputationListResponse(
        items=items,
        total=len(items),
    )


@router.get("/{source_id}/reputation", response_model=SourceReputationResponse)
async def get_source_reputation(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Get the complete evidence-driven reputation profile and 9-factor decomposition for a specific source.
    """
    profile = await source_reputation_service.build_source_reputation(source_id=source_id, db=db)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SOURCE_NOT_FOUND",
                "message": f"Source with ID {source_id} was not found",
                "details": {"source_id": source_id},
            },
        )

    # Privacy filtering
    if (not current_user or current_user.role in (UserRole.PUBLIC.value, UserRole.CITIZEN.value)) and profile.source_type == SourceType.CITIZEN.value:
        profile.source_name = f"Citizen Contributor #{profile.source_id[:6]}"

    return profile


@router.get("/{source_id}/reputation/timeline", response_model=SourceReputationTimelineResponse)
async def get_source_reputation_timeline(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Retrieve the chronological reputation and verification milestone timeline for a source.
    """
    timeline = await source_reputation_service.get_source_reputation_timeline(source_id=source_id, db=db)
    if not timeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SOURCE_NOT_FOUND",
                "message": f"Source with ID {source_id} was not found",
                "details": {"source_id": source_id},
            },
        )
    return timeline


@router.get("/{source_id}/reputation/categories", response_model=SourceReputationCategoriesResponse)
async def get_source_reputation_categories(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Retrieve category-specific reliability breakdowns for a source (e.g. RAINFALL vs FOG vs THUNDERSTORM).
    """
    categories = await source_reputation_service.get_source_category_reputation(source_id=source_id, db=db)
    if not categories:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SOURCE_NOT_FOUND",
                "message": f"Source with ID {source_id} was not found",
                "details": {"source_id": source_id},
            },
        )
    return categories


@router.get("/{source_id}/reputation/evidence", response_model=SourceReputationEvidenceResponse)
async def get_source_reputation_evidence(
    source_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ANALYST, UserRole.ADMIN, UserRole.GOVERNMENT)),
):
    """
    Retrieve historical evidence items and reports produced by this source (Analyst/Admin only).
    """
    evidence = await source_reputation_service.get_source_reputation_evidence(
        source_id=source_id,
        db=db,
        limit=limit,
    )
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SOURCE_NOT_FOUND",
                "message": f"Source with ID {source_id} was not found",
                "details": {"source_id": source_id},
            },
        )
    return evidence


# =========================================================================
# Standard Source & Connector Endpoints
# =========================================================================

@router.get("", response_model=List[SourceResponse])
async def list_sources(
    source_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all registered data sources, connectors, and their current health/trust metrics."""
    query = select(Source).options(selectinload(Source.health))
    if source_type:
        query = query.where(Source.source_type == source_type.upper())
    if is_active is not None:
        query = query.where(Source.is_active == is_active)

    query = query.order_by(Source.name.asc())
    result = await db.execute(query)
    sources = result.scalars().all()

    return [_build_source_response(s) for s in sources]


@router.get("/{source_id}", response_model=SourceResponse)
async def get_single_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get metadata, connector status, and trust score for a specific source."""
    try:
        s_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_UUID",
                "message": "Provided source ID is not a valid UUID",
                "details": {"source_id": source_id},
            },
        )

    query = select(Source).options(selectinload(Source.health)).where(Source.id == s_uuid)
    result = await db.execute(query)
    source = result.scalars().first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SOURCE_NOT_FOUND",
                "message": f"Source with ID {source_id} was not found",
                "details": {"source_id": source_id},
            },
        )
    return _build_source_response(source)


@router.get("/{source_id}/trust-history", response_model=TrustHistoryResponse)
async def get_source_trust_history(
    source_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve chronological trust score audit history and adjustments for a source."""
    try:
        s_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_UUID",
                "message": "Provided source ID is not a valid UUID",
                "details": {"source_id": source_id},
            },
        )

    s_res = await db.execute(select(Source).where(Source.id == s_uuid))
    source = s_res.scalars().first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SOURCE_NOT_FOUND",
                "message": f"Source with ID {source_id} was not found",
                "details": {"source_id": source_id},
            },
        )

    h_query = (
        select(SourceReputationHistory)
        .where(SourceReputationHistory.source_id == s_uuid)
        .order_by(desc(SourceReputationHistory.recorded_at))
        .limit(100)
    )
    h_res = await db.execute(h_query)
    entries = h_res.scalars().all()

    history_items = [
        TrustHistoryEntry(
            recorded_at=entry.recorded_at,
            old_score=entry.old_score,
            new_score=entry.new_score,
            outcome=entry.outcome,
            triggering_event_id=str(entry.triggering_event_id) if entry.triggering_event_id else None,
        )
        for entry in entries
    ]

    return TrustHistoryResponse(
        source_id=str(source.id),
        current_trust_score=source.trust_score,
        history=history_items,
    )


@router.post(
    "/connectors",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def create_connector(
    data: CreateConnectorRequest,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Register a new external data source / connector (Admin only)."""
    source = Source(
        name=data.name,
        source_type=data.source_type.upper(),
        connector_class=data.connector_class,
        config=data.config,
        trust_score=0.7 if data.source_type.upper() == "WEATHER_API" else 0.5,
        is_active=True,
        is_demo=data.is_demo,
    )
    db.add(source)
    await db.flush()

    health = ConnectorHealth(
        source_id=source.id,
        status=ConnectorStatus.HEALTHY.value,
        records_ingested_last_hour=0,
    )
    db.add(health)
    await db.flush()

    await log_audit_event(
        db=db,
        action_type=AuditActionType.CREATE.value,
        entity_type="Source",
        entity_id=source.id,
        user_id=current_user.id,
        new_value={"name": source.name, "connector_class": source.connector_class},
        request=request,
    )
    await db.commit()
    await db.refresh(source)
    source.health = health

    return _build_source_response(source)


@router.patch(
    "/connectors/{source_id}",
    response_model=SourceResponse,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def update_connector(
    source_id: str,
    data: UpdateConnectorRequest,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Enable, disable, or reconfigure an existing connector (Admin only)."""
    try:
        s_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_UUID",
                "message": "Provided source ID is not a valid UUID",
                "details": {"source_id": source_id},
            },
        )

    query = select(Source).options(selectinload(Source.health)).where(Source.id == s_uuid)
    result = await db.execute(query)
    source = result.scalars().first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SOURCE_NOT_FOUND",
                "message": f"Source with ID {source_id} was not found",
                "details": {"source_id": source_id},
            },
        )

    old_vals = {"is_active": source.is_active, "config": source.config}

    if data.is_active is not None:
        source.is_active = data.is_active
    if data.config is not None:
        source.config = data.config

    action = AuditActionType.CONNECTOR_ENABLE.value if data.is_active else AuditActionType.CONNECTOR_DISABLE.value
    await log_audit_event(
        db=db,
        action_type=action,
        entity_type="Source",
        entity_id=source.id,
        user_id=current_user.id,
        old_value=old_vals,
        new_value={"is_active": source.is_active, "config": source.config},
        request=request,
    )
    await db.commit()
    query = select(Source).options(selectinload(Source.health)).where(Source.id == s_uuid)
    result = await db.execute(query)
    source = result.scalars().first()

    return _build_source_response(source)
