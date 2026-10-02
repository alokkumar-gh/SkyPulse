import uuid
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload

from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.models.verification import VerificationResult as DBVerificationResult, VerificationEvidence
from app.models.enums import VerificationStatus, VerificationMethod
from app.schemas.verification import (
    VerificationResult as SchemaVerificationResult,
    VerificationQueueItem,
    ManualOverrideRequest,
    VerificationEvidenceItem,
)


async def get_verification_queue(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[int] = None,
) -> Tuple[List[VerificationQueueItem], int]:
    query = select(WeatherEvent).where(WeatherEvent.is_deleted == False)

    if status:
        query = query.where(WeatherEvent.verification_status == status.upper())
    else:
        # Default queue shows unverified or requires review
        query = query.where(
            WeatherEvent.verification_status.in_(
                [VerificationStatus.REQUIRES_REVIEW.value, VerificationStatus.UNVERIFIED.value]
            )
        )

    if state:
        query = query.where(WeatherEvent.primary_state.ilike(f"%{state}%"))
    if district:
        query = query.where(WeatherEvent.primary_district.ilike(f"%{district}%"))
    if category:
        query = query.where(WeatherEvent.category == category.upper())
    if severity is not None:
        query = query.where(WeatherEvent.severity == severity)

    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    offset = (page - 1) * per_page
    query = query.order_by(desc(WeatherEvent.first_reported_at)).offset(offset).limit(per_page)
    result = await db.execute(query)
    events = result.scalars().all()

    items = [
        VerificationQueueItem(
            event_id=str(e.id),
            category=e.category,
            severity=e.severity,
            confidence_score=e.confidence_score,
            verification_status=e.verification_status,
            state=e.primary_state,
            first_reported_at=e.first_reported_at,
            evidence_count=e.evidence_count,
        )
        for e in events
    ]
    return items, total


async def get_verification_for_event(
    db: AsyncSession,
    event_id: uuid.UUID,
) -> Optional[SchemaVerificationResult]:
    query = (
        select(DBVerificationResult)
        .options(selectinload(DBVerificationResult.evidence_signals))
        .where(DBVerificationResult.canonical_event_id == event_id)
    )
    result = await db.execute(query)
    vr = result.scalars().first()
    if not vr:
        # Check if event exists
        e_res = await db.execute(select(WeatherEvent).where(WeatherEvent.id == event_id))
        ev = e_res.scalars().first()
        if not ev:
            return None
        return SchemaVerificationResult(
            event_id=str(ev.id),
            status=ev.verification_status,
            confidence_score=ev.confidence_score,
            explanation_text="Pending verification analysis",
            evidence_items=[],
            signal_scores={},
            method="UNVERIFIED",
            is_manual_override=False,
            created_at=ev.created_at,
        )

    evidence_items = [
        VerificationEvidenceItem(
            evidence_type=item.get("evidence_type", "OFFICIAL_API") if isinstance(item, dict) else item.evidence_type,
            source_name=item.get("source_name") if isinstance(item, dict) else item.source_name,
            description=item.get("description") if isinstance(item, dict) else item.description,
            weight_contribution=item.get("weight_contribution") if isinstance(item, dict) else item.weight_contribution,
        )
        for item in (vr.evidence_items or [])
    ]

    return SchemaVerificationResult(
        event_id=str(vr.canonical_event_id),
        status=vr.status,
        confidence_score=vr.confidence_score,
        explanation_text=vr.explanation_text,
        evidence_items=evidence_items,
        signal_scores=vr.signal_scores or {},
        method=vr.method,
        is_manual_override=vr.is_manual_override,
        created_at=vr.created_at,
    )


async def apply_manual_override(
    db: AsyncSession,
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    data: ManualOverrideRequest,
) -> SchemaVerificationResult:
    # 1. Update event status
    e_res = await db.execute(select(WeatherEvent).where(WeatherEvent.id == event_id))
    event = e_res.scalars().first()
    if not event:
        raise ValueError("Weather event not found")

    new_status = data.status.upper()
    event.verification_status = new_status
    event.last_updated_at = datetime.now(timezone.utc)

    # 2. Update or create VerificationResult
    vr_res = await db.execute(
        select(DBVerificationResult).where(DBVerificationResult.canonical_event_id == event_id)
    )
    vr = vr_res.scalars().first()

    if not vr:
        vr = DBVerificationResult(
            canonical_event_id=event.id,
            reviewed_by=user_id,
            status=new_status,
            confidence_score=1.0 if new_status == VerificationStatus.VERIFIED.value else 0.8,
            explanation_text=data.reason,
            evidence_items=[{"evidence_type": "ANALYST_NOTE", "description": data.reason}],
            signal_scores={"manual_override": 1.0},
            method=VerificationMethod.MANUAL.value,
            is_manual_override=True,
            manual_reason=data.reason,
        )
        db.add(vr)
    else:
        vr.status = new_status
        vr.reviewed_by = user_id
        vr.is_manual_override = True
        vr.manual_reason = data.reason
        vr.method = VerificationMethod.MANUAL.value
        vr.explanation_text = f"Manual override by analyst: {data.reason}"

    await db.commit()
    await db.refresh(vr)

    # Trigger dynamic source reputation updates for contributing sources
    try:
        from app.services.source_reputation_service import source_reputation_service
        rep_query = select(WeatherReport.source_id).where(WeatherReport.canonical_event_id == event_id)
        rep_res = await db.execute(rep_query)
        source_ids = set(rep_res.scalars().all())
        for sid in source_ids:
            if sid:
                await source_reputation_service.record_verification_outcome(
                    source_id=sid,
                    outcome=new_status,
                    event_id=event_id,
                    db=db,
                )
    except Exception:
        pass

    evidence_items = [
        VerificationEvidenceItem(
            evidence_type=item.get("evidence_type", "ANALYST_NOTE"),
            source_name=item.get("source_name", "Analyst Override"),
            description=item.get("description", data.reason),
            weight_contribution=1.0,
        )
        for item in (vr.evidence_items or [])
    ]

    return SchemaVerificationResult(
        event_id=str(vr.canonical_event_id),
        status=vr.status,
        confidence_score=vr.confidence_score,
        explanation_text=vr.explanation_text,
        evidence_items=evidence_items,
        signal_scores=vr.signal_scores or {},
        method=vr.method,
        is_manual_override=vr.is_manual_override,
        created_at=vr.created_at,
    )
