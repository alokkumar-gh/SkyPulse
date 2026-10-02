"""
Ingestion History & Persistent Telemetry Service.
Provides PostgreSQL-backed persistence, idempotent record storage,
historical querying, multi-granularity time aggregations (hourly/daily/weekly),
source comparison matrices, and retention cleanup.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.ingestion_run import IngestionRunRecord, IngestionPayloadArchive
from app.schemas.orchestration import (
    IngestionRunResponse,
    IngestionRunStatusEnum,
    HistoricalAggregationIntervalEnum,
    HistoricalTelemetryBucket,
    HistoricalTelemetryResponse,
    HistoricalSourceComparisonRow,
    HistoricalSourceComparisonResponse,
    HistoricalPerformanceSummaryResponse,
    SourcePerformanceMetrics,
    PipelineStageTelemetry,
    PruneHistoryResponse,
)

logger = logging.getLogger("skypulse.ingestion_history")


class IngestionHistoryService:
    """
    Authoritative database repository for persistent ingestion history.
    Guarantees isolation: DB failure never crashes connector execution.
    """

    @staticmethod
    async def persist_ingestion_run(
        run: IngestionRunResponse,
        session: Optional[AsyncSession] = None,
    ) -> bool:
        """
        Persists a completed IngestionRunResponse into PostgreSQL.
        Idempotent: Duplicate run_ids are ignored or safely updated.
        Fault-tolerant: Returns False on database error without throwing.
        """
        async def _do_persist(db: AsyncSession) -> bool:
            try:
                # Check for existing run (idempotency)
                existing = await db.scalar(
                    select(IngestionRunRecord).where(IngestionRunRecord.run_id == run.run_id)
                )
                if existing:
                    logger.debug("Ingestion run '%s' already persisted, skipping duplicate.", run.run_id)
                    return True

                error_summary = "; ".join(run.errors[:3]) if run.errors else None
                rec = IngestionRunRecord(
                    id=uuid.uuid4(),
                    run_id=run.run_id,
                    connector_id=run.connector_id,
                    display_name=run.display_name,
                    source_family=run.source_family,
                    status=run.status.value,
                    started_at=run.started_at,
                    completed_at=run.completed_at or run.started_at,
                    duration_ms=run.duration_ms,
                    records_fetched=run.records_fetched,
                    weather_relevant=run.weather_relevant,
                    india_valid=run.india_valid,
                    unknown_location=run.unknown_location,
                    quarantined=run.quarantined,
                    duplicates=run.duplicates,
                    accepted=run.accepted,
                    classified=run.classified,
                    verified=run.verified,
                    failed=run.failed,
                    error_count=run.error_count,
                    error_summary=error_summary,
                    errors_json=run.errors,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                db.add(rec)
                await db.commit()
                logger.info("Persisted ingestion run '%s' [%s] status=%s", run.run_id, run.connector_id, run.status.value)
                return True
            except Exception as exc:
                await db.rollback()
                logger.error("Failed persisting ingestion run '%s' to database: %s", run.run_id, exc)
                return False

        if session is not None:
            return await _do_persist(session)

        try:
            async with async_session_factory() as new_session:
                return await _do_persist(new_session)
        except Exception as exc:
            logger.error("Database connection failure while persisting run '%s': %s", run.run_id, exc)
            return False

    @staticmethod
    async def get_historical_runs(
        connector_id: Optional[str] = None,
        source_family: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
        session: Optional[AsyncSession] = None,
    ) -> Tuple[List[IngestionRunResponse], int]:
        """Queries persisted historical runs with filtering, ordering, and pagination."""
        async def _do_query(db: AsyncSession) -> Tuple[List[IngestionRunResponse], int]:
            conditions = []
            if connector_id:
                conditions.append(IngestionRunRecord.connector_id == connector_id)
            if source_family:
                conditions.append(IngestionRunRecord.source_family == source_family)
            if status:
                conditions.append(IngestionRunRecord.status == status)
            if start_date:
                conditions.append(IngestionRunRecord.started_at >= start_date)
            if end_date:
                conditions.append(IngestionRunRecord.started_at <= end_date)

            where_clause = and_(*conditions) if conditions else True

            # Count total matching
            count_stmt = select(func.count(IngestionRunRecord.id)).where(where_clause)
            total = await db.scalar(count_stmt) or 0

            # Fetch rows
            stmt = (
                select(IngestionRunRecord)
                .where(where_clause)
                .order_by(IngestionRunRecord.started_at.desc())
                .offset(offset)
                .limit(min(limit, 500))
            )
            rows = (await db.scalars(stmt)).all()

            results = [
                IngestionRunResponse(
                    run_id=r.run_id,
                    connector_id=r.connector_id,
                    display_name=r.display_name,
                    source_family=r.source_family,
                    started_at=r.started_at if (r.started_at is None or r.started_at.tzinfo is not None) else r.started_at.replace(tzinfo=timezone.utc),
                    completed_at=r.completed_at if (r.completed_at is None or r.completed_at.tzinfo is not None) else r.completed_at.replace(tzinfo=timezone.utc),
                    duration_ms=r.duration_ms,
                    status=IngestionRunStatusEnum(r.status),
                    records_fetched=r.records_fetched,
                    weather_relevant=r.weather_relevant,
                    india_valid=r.india_valid,
                    unknown_location=r.unknown_location,
                    quarantined=r.quarantined,
                    duplicates=r.duplicates,
                    accepted=r.accepted,
                    classified=r.classified,
                    verified=r.verified,
                    failed=r.failed,
                    error_count=r.error_count,
                    errors=r.errors_json or [],
                )
                for r in rows
            ]
            return results, total

        if session is not None:
            return await _do_query(session)

        async with async_session_factory() as db:
            return await _do_query(db)

    @staticmethod
    async def get_historical_telemetry_aggregation(
        interval: str = "daily",
        connector_id: Optional[str] = None,
        source_family: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        session: Optional[AsyncSession] = None,
    ) -> HistoricalTelemetryResponse:
        """
        Aggregates persistent ingestion runs into hourly, daily, or weekly time buckets.
        Only returns time buckets with actual historical records (zero fake history).
        """
        async def _do_agg(db: AsyncSession) -> HistoricalTelemetryResponse:
            conditions = []
            if connector_id:
                conditions.append(IngestionRunRecord.connector_id == connector_id)
            if source_family:
                conditions.append(IngestionRunRecord.source_family == source_family)
            if start_date:
                conditions.append(IngestionRunRecord.started_at >= start_date)
            if end_date:
                conditions.append(IngestionRunRecord.started_at <= end_date)

            where_clause = and_(*conditions) if conditions else True

            stmt = (
                select(IngestionRunRecord)
                .where(where_clause)
                .order_by(IngestionRunRecord.started_at.asc())
            )
            records = (await db.scalars(stmt)).all()

            if not records:
                return HistoricalTelemetryResponse(
                    interval=interval,
                    connector_id=connector_id,
                    source_family=source_family,
                    start_date=start_date,
                    end_date=end_date,
                    total_buckets=0,
                    buckets=[],
                )

            # Group into time buckets
            buckets_map: Dict[str, Dict[str, Any]] = {}
            for rec in records:
                t = rec.started_at
                if interval == "hourly":
                    b_start = datetime(t.year, t.month, t.day, t.hour, tzinfo=timezone.utc)
                    b_end = b_start + timedelta(hours=1)
                elif interval == "weekly":
                    # Start of week (Monday)
                    b_start = datetime(t.year, t.month, t.day, tzinfo=timezone.utc) - timedelta(days=t.weekday())
                    b_end = b_start + timedelta(days=7)
                else:  # daily
                    b_start = datetime(t.year, t.month, t.day, tzinfo=timezone.utc)
                    b_end = b_start + timedelta(days=1)

                k = b_start.isoformat()
                if k not in buckets_map:
                    buckets_map[k] = {
                        "bucket_start": b_start,
                        "bucket_end": b_end,
                        "total_runs": 0,
                        "successful_runs": 0,
                        "failed_runs": 0,
                        "records_fetched": 0,
                        "weather_relevant": 0,
                        "india_valid": 0,
                        "quarantined": 0,
                        "duplicates": 0,
                        "accepted": 0,
                        "classified": 0,
                        "verified": 0,
                        "failed": 0,
                        "error_count": 0,
                        "total_duration_ms": 0.0,
                    }

                b = buckets_map[k]
                b["total_runs"] += 1
                if rec.status == IngestionRunStatusEnum.SUCCESS.value:
                    b["successful_runs"] += 1
                elif rec.status == IngestionRunStatusEnum.FAILED.value:
                    b["failed_runs"] += 1

                b["records_fetched"] += rec.records_fetched
                b["weather_relevant"] += rec.weather_relevant
                b["india_valid"] += rec.india_valid
                b["quarantined"] += rec.quarantined
                b["duplicates"] += rec.duplicates
                b["accepted"] += rec.accepted
                b["classified"] += rec.classified
                b["verified"] += rec.verified
                b["failed"] += rec.failed
                b["error_count"] += rec.error_count
                b["total_duration_ms"] += rec.duration_ms

            # Compute operational rates for each bucket
            result_buckets: List[HistoricalTelemetryBucket] = []
            for k in sorted(buckets_map.keys()):
                b = buckets_map[k]
                runs = b["total_runs"]
                fetched = max(b["records_fetched"], 1)
                w_rel = max(b["weather_relevant"], 1)
                acc = max(b["accepted"], 1)

                bucket_item = HistoricalTelemetryBucket(
                    bucket_start=b["bucket_start"],
                    bucket_end=b["bucket_end"],
                    total_runs=runs,
                    successful_runs=b["successful_runs"],
                    failed_runs=b["failed_runs"],
                    records_fetched=b["records_fetched"],
                    weather_relevant=b["weather_relevant"],
                    india_valid=b["india_valid"],
                    quarantined=b["quarantined"],
                    duplicates=b["duplicates"],
                    accepted=b["accepted"],
                    classified=b["classified"],
                    verified=b["verified"],
                    failed=b["failed"],
                    error_count=b["error_count"],
                    fetch_success_rate=round(b["successful_runs"] / max(runs, 1), 4),
                    processing_success_rate=round(b["accepted"] / fetched, 4) if b["records_fetched"] > 0 else 0.0,
                    weather_relevance_rate=round(b["weather_relevant"] / fetched, 4) if b["records_fetched"] > 0 else 0.0,
                    india_validation_rate=round(b["india_valid"] / w_rel, 4) if b["weather_relevant"] > 0 else 0.0,
                    duplicate_rate=round(b["duplicates"] / fetched, 4) if b["records_fetched"] > 0 else 0.0,
                    verification_rate=round(b["verified"] / acc, 4) if b["accepted"] > 0 else 0.0,
                    average_duration_ms=round(b["total_duration_ms"] / max(runs, 1), 2),
                )
                result_buckets.append(bucket_item)

            return HistoricalTelemetryResponse(
                interval=interval,
                connector_id=connector_id,
                source_family=source_family,
                start_date=start_date,
                end_date=end_date,
                total_buckets=len(result_buckets),
                buckets=result_buckets,
            )

        if session is not None:
            return await _do_agg(session)

        async with async_session_factory() as db:
            return await _do_agg(db)

    @staticmethod
    async def get_historical_source_comparison(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        session: Optional[AsyncSession] = None,
    ) -> HistoricalSourceComparisonResponse:
        """
        Aggregates historical counts by source family across persisted database runs.
        Returns actual totals for IMD, data.gov.in, GDACS, Social Media, Search Discovery,
        News Websites, Weather APIs, and other registered sources.
        """
        async def _do_comparison(db: AsyncSession) -> HistoricalSourceComparisonResponse:
            conditions = []
            if start_date:
                conditions.append(IngestionRunRecord.started_at >= start_date)
            if end_date:
                conditions.append(IngestionRunRecord.started_at <= end_date)

            where_clause = and_(*conditions) if conditions else True

            stmt = select(IngestionRunRecord).where(where_clause)
            records = (await db.scalars(stmt)).all()

            family_map: Dict[str, Dict[str, Any]] = {}
            for r in records:
                fam = r.source_family
                if fam not in family_map:
                    family_map[fam] = {
                        "source_family": fam,
                        "display_name": r.display_name,
                        "total_runs": 0,
                        "successful_runs": 0,
                        "failed_runs": 0,
                        "records_fetched": 0,
                        "weather_relevant": 0,
                        "india_valid": 0,
                        "duplicates": 0,
                        "accepted": 0,
                        "classified": 0,
                        "verified": 0,
                        "first_run_at": r.started_at,
                        "last_run_at": r.started_at,
                    }

                f = family_map[fam]
                f["total_runs"] += 1
                if r.status == IngestionRunStatusEnum.SUCCESS.value:
                    f["successful_runs"] += 1
                elif r.status == IngestionRunStatusEnum.FAILED.value:
                    f["failed_runs"] += 1

                f["records_fetched"] += r.records_fetched
                f["weather_relevant"] += r.weather_relevant
                f["india_valid"] += r.india_valid
                f["duplicates"] += r.duplicates
                f["accepted"] += r.accepted
                f["classified"] += r.classified
                f["verified"] += r.verified

                if r.started_at < f["first_run_at"]:
                    f["first_run_at"] = r.started_at
                if r.started_at > f["last_run_at"]:
                    f["last_run_at"] = r.started_at

            rows = [
                HistoricalSourceComparisonRow(
                    source_family=d["source_family"],
                    display_name=d["display_name"],
                    total_runs=d["total_runs"],
                    successful_runs=d["successful_runs"],
                    failed_runs=d["failed_runs"],
                    records_fetched=d["records_fetched"],
                    weather_relevant=d["weather_relevant"],
                    india_valid=d["india_valid"],
                    duplicates=d["duplicates"],
                    accepted=d["accepted"],
                    classified=d["classified"],
                    verified=d["verified"],
                    first_run_at=d["first_run_at"],
                    last_run_at=d["last_run_at"],
                )
                for d in family_map.values()
            ]

            return HistoricalSourceComparisonResponse(
                start_date=start_date,
                end_date=end_date,
                total_sources=len(rows),
                sources=rows,
            )

        if session is not None:
            return await _do_comparison(session)

        async with async_session_factory() as db:
            return await _do_comparison(db)

    @staticmethod
    async def get_historical_performance_summary(
        connector_id: Optional[str] = None,
        source_family: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        session: Optional[AsyncSession] = None,
    ) -> HistoricalPerformanceSummaryResponse:
        """Calculates exact aggregate operational metrics directly from PostgreSQL records."""
        async def _do_perf(db: AsyncSession) -> HistoricalPerformanceSummaryResponse:
            conditions = []
            if connector_id:
                conditions.append(IngestionRunRecord.connector_id == connector_id)
            if source_family:
                conditions.append(IngestionRunRecord.source_family == source_family)
            if start_date:
                conditions.append(IngestionRunRecord.started_at >= start_date)
            if end_date:
                conditions.append(IngestionRunRecord.started_at <= end_date)

            where_clause = and_(*conditions) if conditions else True
            records = (await db.scalars(select(IngestionRunRecord).where(where_clause))).all()

            total_runs = len(records)
            succ_runs = 0
            failed_runs = 0
            total_duration = 0.0

            stage = PipelineStageTelemetry()

            for r in records:
                if r.status == IngestionRunStatusEnum.SUCCESS.value:
                    succ_runs += 1
                elif r.status == IngestionRunStatusEnum.FAILED.value:
                    failed_runs += 1

                total_duration += r.duration_ms
                stage.records_fetched += r.records_fetched
                stage.weather_relevant += r.weather_relevant
                stage.india_valid += r.india_valid
                stage.unknown_location += r.unknown_location
                stage.quarantined += r.quarantined
                stage.duplicates += r.duplicates
                stage.accepted += r.accepted
                stage.classified += r.classified
                stage.verified += r.verified
                stage.failed += r.failed

            fetched = max(stage.records_fetched, 1)
            w_rel = max(stage.weather_relevant, 1)
            acc = max(stage.accepted, 1)

            perf = SourcePerformanceMetrics(
                fetch_success_rate=round(succ_runs / max(total_runs, 1), 4) if total_runs > 0 else 0.0,
                processing_success_rate=round(stage.accepted / fetched, 4) if stage.records_fetched > 0 else 0.0,
                weather_relevance_rate=round(stage.weather_relevant / fetched, 4) if stage.records_fetched > 0 else 0.0,
                india_validation_rate=round(stage.india_valid / w_rel, 4) if stage.weather_relevant > 0 else 0.0,
                duplicate_rate=round(stage.duplicates / fetched, 4) if stage.records_fetched > 0 else 0.0,
                verification_rate=round(stage.verified / acc, 4) if stage.accepted > 0 else 0.0,
                average_fetch_duration_ms=round(total_duration / max(total_runs, 1), 2) if total_runs > 0 else 0.0,
                total_processing_time_ms=round(total_duration, 2),
                total_runs_count=total_runs,
                successful_runs_count=succ_runs,
                failed_runs_count=failed_runs,
            )

            return HistoricalPerformanceSummaryResponse(
                connector_id=connector_id,
                source_family=source_family,
                start_date=start_date,
                end_date=end_date,
                metrics=perf,
                stage_totals=stage,
            )

        if session is not None:
            return await _do_perf(session)

        async with async_session_factory() as db:
            return await _do_perf(db)

    @staticmethod
    async def prune_historical_records(
        retention_days: int = 90,
        session: Optional[AsyncSession] = None,
    ) -> PruneHistoryResponse:
        """
        Safely prunes historical ingestion runs older than the configured retention cutoff.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        async def _do_prune(db: AsyncSession) -> PruneHistoryResponse:
            stmt = delete(IngestionRunRecord).where(IngestionRunRecord.started_at < cutoff)
            result = await db.execute(stmt)
            await db.commit()
            deleted_count = result.rowcount or 0
            logger.info("Pruned %d historical ingestion run records older than %s (%d days retention)", deleted_count, cutoff.isoformat(), retention_days)
            return PruneHistoryResponse(
                pruned_records_count=deleted_count,
                retention_days=retention_days,
                cutoff_date=cutoff,
                message=f"Pruned {deleted_count} historical ingestion records older than {retention_days} days.",
            )

        if session is not None:
            return await _do_prune(session)

        async with async_session_factory() as db:
            return await _do_prune(db)


ingestion_history_service = IngestionHistoryService()
