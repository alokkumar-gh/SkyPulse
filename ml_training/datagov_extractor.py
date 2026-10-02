"""
SkyPulse data.gov.in Historical Dataset Extractor.
==================================================
Extracts open government weather datasets (CWC river water levels, OGD rainfall,
heat observations) from database storage into canonical TrainingRecord instances.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.weather_report import WeatherReport
from app.models.source import Source
from ml.schemas import TrainingRecord, LocationMethod, WeatherEventCategory
from ml_training.labeling import labeling_engine
from ml_training.quality import quality_engine, DataQualityStatus

import asyncio
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("skypulse.ml.datagov_extractor")


class DataGovDatasetExtractor:
    """
    Extracts published Indian open government records from database storage.
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
            logger.warning("Database unavailable for data.gov.in extraction: %s", e)
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
        """Queries database for data.gov.in source reports and converts to TrainingRecord objects."""
        src_q = select(Source.id).where(
            (Source.source_type == "GOVERNMENT_DATASET") |
            (Source.connector_class.ilike("%DataGov%")) |
            (Source.name.ilike("%data.gov.in%")) |
            (Source.name.ilike("%Open Government Data%"))
        )
        src_res = await db.execute(src_q)
        datagov_source_ids = src_res.scalars().all()

        if not datagov_source_ids:
            logger.info("No data.gov.in sources registered in database.")
            return []

        query = select(WeatherReport).where(WeatherReport.source_id.in_(datagov_source_ids))
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

            cat, label_type, method, conf, candidates, conflict = labeling_engine.derive_label(
                text=text,
                source_type="DATA_GOV_IN",
                raw_payload=payload,
                verified_status=rep.status,
                source_trust=0.90,
            )

            rec = TrainingRecord(
                id=str(rep.id),
                text=text,
                category=cat,
                severity=rep.severity or 2,
                timestamp=rep.event_time.isoformat() if rep.event_time else (rep.ingested_at.isoformat() if rep.ingested_at else None),
                latitude=rep.location_lat,
                longitude=rep.location_lon,
                source_type="DATA_GOV_IN",
                source_id=str(rep.source_id),
                verified=True,
                verification_status="VERIFIED",
                label_source="DATA_GOV_IN_OGD_DATASET",
                label_confidence=conf,
                label_method=method,
                language=rep.language or "en",
                location_method=LocationMethod.DISTRICT_CENTROID.value if rep.location_district else LocationMethod.EXACT_COORDINATE.value,
                conflict_flag=conflict,
                candidate_labels=candidates,
                metadata={
                    "original_report_id": str(rep.id),
                    "resource_id": payload.get("resource_id"),
                    "agency": payload.get("agency") or "data.gov.in",
                    "location_state": rep.location_state,
                    "location_district": rep.location_district,
                },
            )

            status, _ = quality_engine.validate_record(rec)
            if status != DataQualityStatus.INVALID:
                records.append(rec)

        logger.info("Extracted %d valid training records from data.gov.in datasets", len(records))
        return records


datagov_extractor = DataGovDatasetExtractor()
