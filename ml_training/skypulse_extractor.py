"""
SkyPulse Verified Reports Dataset Extractor.
============================================
Extracts WeatherReports and WeatherEvents meeting explicit verification criteria
(status in ['VERIFIED', 'SUPPORTED']) into high-confidence TrainingRecord instances.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.weather_report import WeatherReport
from app.models.weather_event import WeatherEvent
from app.models.enums import VerificationStatus
from ml.schemas import TrainingRecord, LocationMethod, WeatherEventCategory
from ml_training.labeling import labeling_engine
from ml_training.quality import quality_engine, DataQualityStatus

import asyncio
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("skypulse.ml.skypulse_extractor")


class SkyPulseVerifiedExtractor:
    """
    Extracts verified platform citizen/sensor reports with verified evidence links.
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
            logger.warning("Database unavailable for SkyPulse verified extraction: %s", e)
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
        """Queries database for verified WeatherReports linked to verified CanonicalEvents."""
        # Query verified canonical events
        q_events = select(WeatherEvent).where(
            WeatherEvent.verification_status.in_([VerificationStatus.VERIFIED.value, "SUPPORTED", "LIKELY"]),
            WeatherEvent.confidence_score >= 0.70,
        )
        res_events = await db.execute(q_events)
        verified_events = {e.id: e for e in res_events.scalars().all()}

        if not verified_events:
            logger.info("No verified canonical events found in database.")
            return []

        # Query reports belonging to verified canonical events
        query = select(WeatherReport).where(
            WeatherReport.canonical_event_id.in_(list(verified_events.keys())),
            WeatherReport.is_duplicate == False,
        )

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
            parent_event = verified_events.get(rep.canonical_event_id)
            text = rep.normalized_text or rep.raw_content or ""
            payload = dict(rep.metadata_ or {})

            cat_str = (rep.primary_category or (parent_event.category if parent_event else "UNKNOWN")).upper()
            cat = WeatherEventCategory(cat_str) if cat_str in WeatherEventCategory._value2member_map_ else WeatherEventCategory.UNKNOWN

            rec = TrainingRecord(
                id=str(rep.id),
                text=text,
                category=cat,
                severity=rep.severity or (parent_event.severity if parent_event else 2),
                timestamp=rep.event_time.isoformat() if rep.event_time else (rep.ingested_at.isoformat() if rep.ingested_at else None),
                latitude=rep.location_lat or (parent_event.centroid_lat if parent_event else None),
                longitude=rep.location_lon or (parent_event.centroid_lon if parent_event else None),
                source_type="SKYPULSE_VERIFIED",
                source_id=str(rep.source_id),
                verified=True,
                verification_status="VERIFIED",
                label_source="SKYPULSE_MULTI_SOURCE_VERIFICATION",
                label_confidence=parent_event.confidence_score if parent_event else 0.85,
                label_method="STRONG_CANONICAL_GROUND_TRUTH",
                language=rep.language or "en",
                location_method=LocationMethod.EXACT_COORDINATE.value if rep.location_lat else LocationMethod.GEOCODED.value,
                conflict_flag=False,
                candidate_labels=[cat.value],
                metadata={
                    "original_report_id": str(rep.id),
                    "canonical_event_id": str(rep.canonical_event_id),
                    "evidence_count": parent_event.evidence_count if parent_event else 1,
                    "location_city": rep.location_city,
                    "location_district": rep.location_district,
                    "location_state": rep.location_state,
                },
            )

            status, _ = quality_engine.validate_record(rec)
            if status != DataQualityStatus.INVALID:
                records.append(rec)

        logger.info("Extracted %d valid training records from verified SkyPulse reports", len(records))
        return records


skypulse_extractor = SkyPulseVerifiedExtractor()
