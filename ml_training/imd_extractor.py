"""
SkyPulse IMD Historical Dataset Extractor.
=========================================
Extracts official IMD weather reports, warnings, nowcasts, and AWS/ARG observations
from PostgreSQL storage into normalized TrainingRecord instances.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.weather_report import WeatherReport
from app.models.source import Source
from ml.schemas import TrainingRecord, LocationMethod, WeatherEventCategory
from ml_training.labeling import labeling_engine
from ml_training.quality import quality_engine, DataQualityStatus

import asyncio
from app.db.session import AsyncSessionLocal, create_async_engine

logger = logging.getLogger("skypulse.ml.imd_extractor")


class IMDDatasetExtractor:
    """
    Extracts authoritative IMD records from SkyPulse storage with full provenance.
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url

    def extract(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50000,
    ) -> Dict[str, Any]:
        """Synchronously extracts records from database, handling connection errors gracefully."""
        try:
            return asyncio.run(self._extract_async(start_date=start_date, end_date=end_date, limit=limit))
        except Exception as e:
            logger.warning("Database unavailable for IMD extraction: %s", e)
            return {"status": "NOT_CONFIGURED", "records": [], "error": str(e)}

    async def _extract_async(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50000,
    ) -> Dict[str, Any]:
        async with AsyncSessionLocal() as session:
            records = await self.extract_from_db(session, start_date=start_date, end_date=end_date, limit=limit)
            status = "AVAILABLE" if records else "NO_DATA"
            return {"status": status, "records": [r.model_dump() for r in records]}

    async def extract_from_db(
        self,
        db: AsyncSession,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50000,
    ) -> List[TrainingRecord]:
        """Queries database for IMD source reports and converts to TrainingRecord objects."""
        # Query IMD sources
        src_q = select(Source.id).where(
            (Source.source_type == "GOVERNMENT_API") |
            (Source.connector_class.ilike("%IMD%")) |
            (Source.name.ilike("%IMD%")) |
            (Source.name.ilike("%India Meteorological Department%"))
        )
        src_res = await db.execute(src_q)
        imd_source_ids = src_res.scalars().all()

        if not imd_source_ids:
            logger.info("No IMD sources registered in database.")
            return []

        # Query reports from IMD sources
        query = select(WeatherReport).where(WeatherReport.source_id.in_(imd_source_ids))
        if start_date:
            try:
                dt_start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                query = query.where(WeatherReport.event_time >= dt_start)
            except Exception:
                pass
        if end_date:
            try:
                dt_end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                query = query.where(WeatherReport.event_time <= dt_end)
            except Exception:
                pass

        query = query.order_by(WeatherReport.event_time.asc()).limit(limit)
        res = await db.execute(query)
        reports = res.scalars().all()

        records: List[TrainingRecord] = []
        for rep in reports:
            text = rep.normalized_text or rep.raw_content or ""
            payload = dict(rep.metadata_ or {})

            # Derive label & confidence
            cat, label_type, method, conf, candidates, conflict = labeling_engine.derive_label(
                text=text,
                source_type="IMD",
                raw_payload=payload,
                verified_status=rep.status,
                source_trust=0.95,
            )

            rec = TrainingRecord(
                id=str(rep.id),
                text=text,
                category=cat,
                severity=rep.severity or 2,
                timestamp=rep.event_time.isoformat() if rep.event_time else (rep.ingested_at.isoformat() if rep.ingested_at else None),
                latitude=rep.location_lat,
                longitude=rep.location_lon,
                source_type="IMD",
                source_id=str(rep.source_id),
                verified=True,
                verification_status="VERIFIED",
                label_source="IMD_OFFICIAL_RECORD",
                label_confidence=conf,
                label_method=method,
                language=rep.language or "en",
                location_method=LocationMethod.STATION.value if rep.location_city else LocationMethod.EXACT_COORDINATE.value,
                conflict_flag=conflict,
                candidate_labels=candidates,
                metadata={
                    "original_report_id": str(rep.id),
                    "location_city": rep.location_city,
                    "location_district": rep.location_district,
                    "location_state": rep.location_state,
                    "provider": "IMD",
                },
            )

            status, _ = quality_engine.validate_record(rec)
            if status != DataQualityStatus.INVALID:
                records.append(rec)

        logger.info("Extracted %d valid training records from IMD source reports", len(records))
        return records


imd_extractor = IMDDatasetExtractor()
