import uuid
import math
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, cast, Float
from sqlalchemy.orm import selectinload
from geoalchemy2.elements import WKTElement

from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.models.event_evidence import EventEvidence
from app.models.verification import VerificationResult
from app.models.media import Media
from app.models.source import Source
from app.schemas.event import (
    EventSummary,
    EventDetail,
    EventTimeline,
    TimelineEntry,
    NearbyEvent,
    VerificationSummary,
    EvidenceReportSummary,
    SourceItemSummary,
)
from app.schemas.report import MediaSummary
from app.schemas.common import LocationSchema
from app.services.weather_intelligence_service import synthesize_semantic_event_intelligence


def _build_location_schema(event: WeatherEvent) -> LocationSchema:
    return LocationSchema(
        city=event.primary_city,
        district=event.primary_district,
        state=event.primary_state,
        lat=event.centroid_lat,
        lon=event.centroid_lon,
        confidence="HIGH" if event.centroid_lat else "LOW",
    )


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


async def list_events(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
    q: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[int] = None,
    severity_min: Optional[int] = None,
    status: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_anomalous: Optional[bool] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    min_confidence: Optional[float] = None,
    max_confidence: Optional[float] = None,
    min_evidence_count: Optional[int] = None,
    has_propagation: Optional[bool] = None,
) -> Tuple[List[EventSummary], int]:
    query = select(WeatherEvent).where(
        WeatherEvent.is_deleted == False,
        WeatherEvent.category != "UNKNOWN",
    )

    filters = []
    if q and q.strip():
        q_term = f"%{q.strip()}%"
        filters.append(
            or_(
                WeatherEvent.primary_state.ilike(q_term),
                WeatherEvent.primary_district.ilike(q_term),
                WeatherEvent.primary_city.ilike(q_term),
                WeatherEvent.category.ilike(q_term),
                WeatherEvent.sub_category.ilike(q_term),
            )
        )
    if category:
        filters.append(WeatherEvent.category == category.upper())
    if severity is not None:
        filters.append(WeatherEvent.severity == severity)
    elif severity_min is not None:
        filters.append(WeatherEvent.severity >= severity_min)
    if status:
        filters.append(WeatherEvent.verification_status == status.upper())
    if state:
        filters.append(WeatherEvent.primary_state.ilike(f"%{state}%"))
    if district:
        filters.append(WeatherEvent.primary_district.ilike(f"%{district}%"))
    if is_active is not None:
        filters.append(WeatherEvent.is_active == is_active)
    if is_anomalous is not None:
        filters.append(WeatherEvent.is_anomalous == is_anomalous)
    if from_date:
        if is_active is False:
            filters.append(
                or_(
                    WeatherEvent.last_updated_at >= from_date,
                    WeatherEvent.first_reported_at >= from_date,
                )
            )
        else:
            # Active events are ongoing; include if currently active OR updated/reported within time window
            filters.append(
                or_(
                    WeatherEvent.last_updated_at >= from_date,
                    WeatherEvent.first_reported_at >= from_date,
                    WeatherEvent.is_active == True,
                )
            )
    if to_date:
        filters.append(WeatherEvent.first_reported_at <= to_date)
    if min_confidence is not None:
        filters.append(WeatherEvent.confidence_score >= min_confidence)
    if max_confidence is not None:
        filters.append(WeatherEvent.confidence_score <= max_confidence)
    if min_evidence_count is not None:
        filters.append(WeatherEvent.evidence_count >= min_evidence_count)
    if has_propagation is not None:
        if has_propagation:
            filters.append(WeatherEvent.dweg_node_id.isnot(None))
        else:
            filters.append(WeatherEvent.dweg_node_id.is_(None))

    if filters:
        query = query.where(and_(*filters))

    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    offset = (page - 1) * per_page
    query = query.order_by(desc(WeatherEvent.first_reported_at)).offset(offset).limit(per_page)
    result = await db.execute(query)
    events = result.scalars().all()

    summaries = []
    from app.services.weather_intelligence_service import synthesize_semantic_event_intelligence
    for e in events:
        semantic_intel = synthesize_semantic_event_intelligence(
            category=e.category,
            sub_category=e.sub_category,
            state=e.primary_state,
            district=e.primary_district,
            city=e.primary_city,
            evidence_texts=[],
            publishers=[],
            evidence_count=e.evidence_count,
        )
        summaries.append(
            EventSummary(
                id=str(e.id),
                category=e.category,
                sub_category=semantic_intel["sub_category"],
                phenomenon=semantic_intel["phenomenon"],
                event_nature=semantic_intel["event_nature"],
                temporal_scope=semantic_intel["temporal_scope"],
                is_current_observation=semantic_intel["is_current_observation"],
                evidence_basis=semantic_intel["evidence_basis"],
                severity=e.severity,
                confidence_score=e.confidence_score,
                verification_status=e.verification_status,
                title=semantic_intel["title"],
                summary=semantic_intel["summary"],
                description=semantic_intel["summary"],
                state=e.primary_state,
                district=e.primary_district,
                city=e.primary_city,
                latitude=e.centroid_lat,
                longitude=e.centroid_lon,
                location=_build_location_schema(e),
                first_reported_at=e.first_reported_at,
                last_updated_at=e.last_updated_at,
                evidence_count=e.evidence_count,
                is_anomalous=e.is_anomalous,
                is_active=e.is_active,
                is_demo=e.is_demo,
            )
        )
    return summaries, total


async def get_event_by_id(db: AsyncSession, event_id: uuid.UUID) -> Optional[EventDetail]:
    query = (
        select(WeatherEvent)
        .options(
            selectinload(WeatherEvent.evidence_links),
            selectinload(WeatherEvent.verification_result),
        )
        .where(WeatherEvent.id == event_id, WeatherEvent.is_deleted == False)
    )
    result = await db.execute(query)
    event = result.scalars().first()
    if not event:
        return None

    # Load evidence reports joined with sources
    evidence_reports: List[EvidenceReportSummary] = []
    sources_list: List[SourceItemSummary] = []
    evidence_dicts: List[dict] = []
    publishers: List[str] = []
    report_texts = []

    report_ids = [el.weather_report_id for el in event.evidence_links]
    if report_ids:
        r_query = (
            select(WeatherReport, Source)
            .outerjoin(Source, Source.id == WeatherReport.source_id)
            .where(WeatherReport.id.in_(report_ids))
            .order_by(WeatherReport.ingested_at.desc())
        )
        r_res = await db.execute(r_query)
        reports_with_src = r_res.all()

        for r, src in reports_with_src:
            meta = r.metadata_ or {}
            raw_p = meta.get("raw_payload", {}) if isinstance(meta, dict) else {}
            pub = raw_p.get("publisher") or (src.name if src else "National Weather Sensor / Feed")
            source_name = src.name if src else pub
            source_type = src.source_type if src else r.primary_category
            source_url = raw_p.get("original_url") or raw_p.get("link") or meta.get("source_url") or meta.get("url")
            title_text = raw_p.get("title") or meta.get("title") or (r.normalized_text[:120] if r.normalized_text else None)
            snippet = r.raw_content[:280] if r.raw_content else (r.normalized_text[:280] if r.normalized_text else None)

            if pub and pub not in publishers:
                publishers.append(pub)
            if r.raw_content:
                report_texts.append(r.raw_content)

            ev_summary = EvidenceReportSummary(
                id=str(r.id),
                source_name=source_name,
                source_type=source_type,
                publisher=pub,
                source_url=source_url,
                title=title_text,
                snippet=snippet,
                event_time=r.event_time,
                ingested_at=r.ingested_at,
                severity=r.severity,
                relevance="High spatial-temporal agreement",
                trust_score=src.trust_score if src else 0.85,
            )
            evidence_reports.append(ev_summary)

            sources_list.append(
                SourceItemSummary(
                    source_id=str(src.id) if src else str(r.source_id),
                    source_name=source_name,
                    source_type=source_type,
                    publisher=pub,
                    source_url=source_url,
                    title=title_text,
                    snippet=snippet,
                    published_at=r.event_time,
                    fetched_at=r.ingested_at,
                )
            )

            evidence_dicts.append({
                "report_id": str(r.id),
                "source_name": source_name,
                "source_type": source_type,
                "publisher": pub,
                "source_url": source_url,
                "title": title_text,
                "snippet": snippet,
                "text": r.raw_content,
                "event_time": r.event_time.isoformat() if r.event_time else None,
                "ingested_at": r.ingested_at.isoformat() if r.ingested_at else None,
                "trust_score": src.trust_score if src else 0.85,
            })

    # Verification summary
    ver_summary = None
    if event.verification_result:
        vr = event.verification_result
        ver_summary = VerificationSummary(
            status=vr.status,
            confidence_score=vr.confidence_score,
            explanation=vr.explanation_text,
            evidence_items=vr.evidence_items or [],
            method=vr.method,
            reviewed_by=str(vr.reviewed_by) if vr.reviewed_by else None,
        )

    semantic_intel = synthesize_semantic_event_intelligence(
        category=event.category,
        sub_category=event.sub_category,
        state=event.primary_state,
        district=event.primary_district,
        city=event.primary_city,
        evidence_texts=report_texts,
        publishers=publishers,
        evidence_count=event.evidence_count,
    )

    clean_first = report_texts[0].strip() if report_texts else ""
    desc_text = clean_first[:280] + ("..." if len(clean_first) > 280 else "") if clean_first else semantic_intel["summary"]

    return EventDetail(
        id=str(event.id),
        category=event.category,
        sub_category=semantic_intel["sub_category"],
        phenomenon=semantic_intel["phenomenon"],
        event_nature=semantic_intel["event_nature"],
        temporal_scope=semantic_intel["temporal_scope"],
        is_current_observation=semantic_intel["is_current_observation"],
        evidence_basis=semantic_intel["evidence_basis"],
        severity=event.severity,
        confidence_score=event.confidence_score,
        verification_status=event.verification_status,
        title=semantic_intel["title"],
        summary=semantic_intel["summary"],
        description=desc_text,
        state=event.primary_state,
        district=event.primary_district,
        city=event.primary_city,
        latitude=event.centroid_lat,
        longitude=event.centroid_lon,
        location=_build_location_schema(event),
        first_reported_at=event.first_reported_at,
        last_updated_at=event.last_updated_at,
        resolved_at=event.resolved_at,
        evidence_count=event.evidence_count,
        sources_count=len(sources_list) or 1,
        publishers=publishers,
        sources=sources_list,
        is_anomalous=event.is_anomalous,
        anomaly_z_score=event.anomaly_z_score,
        verification=ver_summary,
        evidence_reports=evidence_reports,
        evidence=evidence_dicts,
        media_gallery=[],
        is_demo=event.is_demo,
    )


async def get_event_timeline(db: AsyncSession, event_id: uuid.UUID) -> Optional[EventTimeline]:
    query = (
        select(WeatherEvent)
        .options(selectinload(WeatherEvent.evidence_links))
        .where(WeatherEvent.id == event_id, WeatherEvent.is_deleted == False)
    )
    result = await db.execute(query)
    event = result.scalars().first()
    if not event:
        return None

    timeline_entries: List[TimelineEntry] = []
    report_ids = [el.weather_report_id for el in event.evidence_links]
    if report_ids:
        r_query = (
            select(WeatherReport)
            .options(selectinload(WeatherReport.source))
            .where(WeatherReport.id.in_(report_ids))
            .order_by(WeatherReport.ingested_at.asc())
        )
        r_res = await db.execute(r_query)
        reports = r_res.scalars().all()
        for r in reports:
            timeline_entries.append(
                TimelineEntry(
                    timestamp=r.event_time or r.ingested_at,
                    report_id=str(r.id),
                    source_type=r.source.source_type if r.source else "UNKNOWN",
                    source_name=r.source.name if r.source else "Unknown",
                    severity=r.severity,
                    location=LocationSchema(
                        city=r.location_city,
                        district=r.location_district,
                        state=r.location_state,
                        lat=r.location_lat,
                        lon=r.location_lon,
                    ),
                    summary=r.normalized_text or r.raw_content,
                )
            )

    return EventTimeline(event_id=str(event.id), timeline=timeline_entries)


async def get_nearby_events(
    db: AsyncSession,
    lat: float,
    lon: float,
    radius_km: float = 50.0,
    limit: int = 10,
) -> List[NearbyEvent]:
    # PostGIS distance query with Python fallback
    try:
        from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_SetSRID, ST_MakePoint
        # In PostGIS, geography ST_DWithin uses meters
        point_geom = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        query = (
            select(
                WeatherEvent,
                func.ST_Distance(
                    cast(WeatherEvent.centroid_point, func.geography),
                    cast(point_geom, func.geography),
                ).label("dist_meters"),
            )
            .where(
                WeatherEvent.is_deleted == False,
                WeatherEvent.centroid_point.isnot(None),
                func.ST_DWithin(
                    cast(WeatherEvent.centroid_point, func.geography),
                    cast(point_geom, func.geography),
                    radius_km * 1000.0,
                ),
            )
            .order_by("dist_meters")
            .limit(limit)
        )
        result = await db.execute(query)
        rows = result.all()
        nearby = []
        for e, dist_m in rows:
            dist_km = round(dist_m / 1000.0, 2) if dist_m is not None else None
            summary_dict = EventSummary(
                id=str(e.id),
                category=e.category,
                sub_category=e.sub_category,
                severity=e.severity,
                confidence_score=e.confidence_score,
                verification_status=e.verification_status,
                location=_build_location_schema(e),
                first_reported_at=e.first_reported_at,
                last_updated_at=e.last_updated_at,
                evidence_count=e.evidence_count,
                is_anomalous=e.is_anomalous,
                is_active=e.is_active,
                is_demo=e.is_demo,
            ).model_dump()
            nearby.append(NearbyEvent(**summary_dict, distance_km=dist_km))
        return nearby
    except Exception:
        # Fallback to in-memory Haversine calculation for SQLite/mock environments
        query = (
            select(WeatherEvent)
            .where(
                WeatherEvent.is_deleted == False,
                WeatherEvent.centroid_lat.isnot(None),
                WeatherEvent.centroid_lon.isnot(None),
            )
            .limit(100)
        )
        result = await db.execute(query)
        events = result.scalars().all()
        scored = []
        for e in events:
            d = _haversine_km(lat, lon, e.centroid_lat, e.centroid_lon)
            if d <= radius_km:
                scored.append((e, round(d, 2)))
        scored.sort(key=lambda x: x[1])

        nearby = []
        for e, d in scored[:limit]:
            summary_dict = EventSummary(
                id=str(e.id),
                category=e.category,
                sub_category=e.sub_category,
                severity=e.severity,
                confidence_score=e.confidence_score,
                verification_status=e.verification_status,
                location=_build_location_schema(e),
                first_reported_at=e.first_reported_at,
                last_updated_at=e.last_updated_at,
                evidence_count=e.evidence_count,
                is_anomalous=e.is_anomalous,
                is_active=e.is_active,
                is_demo=e.is_demo,
            ).model_dump()
            nearby.append(NearbyEvent(**summary_dict, distance_km=d))
        return nearby
