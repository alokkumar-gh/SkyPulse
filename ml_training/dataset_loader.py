"""
SkyPulse Training Dataset Ingestion & Assembly Pipeline.

Combines:
1. Official IMD weather bulletins / descriptions
2. data.gov.in public weather observations
3. Curated historical meteorological event texts
4. SkyPulse verified citizen reports

Formats all records to the canonical SkyPulse training schema:
{
    "text": str,
    "category": str,
    "severity": int,
    "timestamp": str,
    "latitude": float,
    "longitude": float,
    "source_type": str,
    "source_id": str,
    "verified": bool,
    "language": str,
    "metadata": dict
}
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

try:
    from ml.schemas import TrainingRecord, WeatherEventCategory
except ImportError:
    from backend.ml.schemas import TrainingRecord, WeatherEventCategory

logger = logging.getLogger("skypulse.ml_dataset")

CANONICAL_CATEGORIES = {cat.value for cat in WeatherEventCategory}


def validate_and_normalize_record(raw: Dict[str, Any]) -> Optional[TrainingRecord]:
    """Validate a raw record and normalize it to the canonical TrainingRecord schema."""
    text = (raw.get("text") or raw.get("raw_content") or raw.get("normalized_text") or "").strip()
    if not text or len(text) < 5:
        return None

    category_raw = (raw.get("category") or raw.get("primary_category") or "UNKNOWN").upper().strip()
    if category_raw not in CANONICAL_CATEGORIES:
        category_raw = "UNKNOWN"

    severity = int(raw.get("severity", 2))
    if severity < 1 or severity > 4:
        severity = 2

    return TrainingRecord(
        text=text,
        category=WeatherEventCategory(category_raw),
        severity=severity,
        timestamp=raw.get("timestamp") or raw.get("event_time") or datetime.now(timezone.utc).isoformat(),
        latitude=raw.get("latitude") or raw.get("location_lat"),
        longitude=raw.get("longitude") or raw.get("location_lon"),
        source_type=raw.get("source_type", "HISTORICAL"),
        source_id=str(raw.get("source_id", "curated")),
        verified=bool(raw.get("verified", False)),
        language=raw.get("language", "en"),
        metadata=raw.get("metadata", {}),
    )


def export_dataset_jsonl(records: List[TrainingRecord], output_path: str) -> int:
    """Export canonical training records to JSONL file."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(rec.model_dump_json() + "\n")
            count += 1
    logger.info("Exported %d training records to %s", count, output_path)
    return count


def load_dataset_jsonl(file_path: str) -> List[TrainingRecord]:
    """Load canonical training records from a JSONL file."""
    if not os.path.exists(file_path):
        logger.warning("Dataset file %s does not exist", file_path)
        return []
    records = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            records.append(TrainingRecord(**data))
    return records


def load_dataset_splits(dataset_dir: str) -> Dict[str, Any]:
    """Load train, val, and test splits along with manifest from a dataset directory."""
    manifest_path = os.path.join(dataset_dir, "dataset_manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    return {
        "manifest": manifest,
        "train": load_dataset_jsonl(os.path.join(dataset_dir, "train.jsonl")),
        "val": load_dataset_jsonl(os.path.join(dataset_dir, "val.jsonl")),
        "test": load_dataset_jsonl(os.path.join(dataset_dir, "test.jsonl")),
    }

