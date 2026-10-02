import csv
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple
from io import TextIOBase

from connectors.schema import CanonicalRawEvent
from connectors.normalizer import INDIA_LAT_MIN, INDIA_LAT_MAX, INDIA_LON_MIN, INDIA_LON_MAX

logger = logging.getLogger("skypulse.batch")


class HistoricalBatchIngestion:
    """
    Streaming chunked ingestion engine for historical weather datasets (CSV / JSON Lines).
    Processes files row-by-row without loading the entire dataset into RAM.
    """

    def __init__(self, source_id: Optional[str] = None):
        self.source_id = source_id or str(uuid.uuid4())

    async def ingest_csv_stream(
        self,
        file_obj: TextIOBase,
        batch_size: int = 100,
    ) -> AsyncGenerator[Tuple[List[CanonicalRawEvent], List[Dict[str, Any]]], None]:
        """
        Yields batches of (valid_events, invalid_row_errors) from a CSV stream.
        Expected columns: description/text, latitude, longitude, observed_at, category, severity, city, state.
        """
        reader = csv.DictReader(file_obj)
        batch: List[CanonicalRawEvent] = []
        errors: List[Dict[str, Any]] = []
        row_num = 1

        for row in reader:
            row_num += 1
            event, err = self._validate_and_parse_row(row, row_num)
            if err:
                errors.append(err)
            elif event:
                batch.append(event)

            if len(batch) >= batch_size:
                yield batch, errors
                batch = []
                errors = []

        if batch or errors:
            yield batch, errors

    async def ingest_jsonl_stream(
        self,
        file_obj: TextIOBase,
        batch_size: int = 100,
    ) -> AsyncGenerator[Tuple[List[CanonicalRawEvent], List[Dict[str, Any]]], None]:
        """Yields batches of (valid_events, invalid_row_errors) from a JSON Lines stream."""
        batch: List[CanonicalRawEvent] = []
        errors: List[Dict[str, Any]] = []
        line_num = 0

        for line in file_obj:
            line_num += 1
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                event, err = self._validate_and_parse_row(row, line_num)
                if err:
                    errors.append(err)
                elif event:
                    batch.append(event)
            except Exception as e:
                errors.append({"line": line_num, "error": f"Invalid JSON: {str(e)}", "data": line[:100]})

            if len(batch) >= batch_size:
                yield batch, errors
                batch = []
                errors = []

        if batch or errors:
            yield batch, errors

    def _validate_and_parse_row(
        self, row: Dict[str, Any], row_id: int
    ) -> Tuple[Optional[CanonicalRawEvent], Optional[Dict[str, Any]]]:
        # Required content
        text = row.get("description") or row.get("text") or row.get("content")
        if not text or not str(text).strip():
            return None, {"row": row_id, "error": "Missing description/text field", "data": row}

        # Optional coordinates validation
        lat = None
        lon = None
        raw_lat = row.get("latitude") or row.get("lat")
        raw_lon = row.get("longitude") or row.get("lon")

        if raw_lat is not None and str(raw_lat).strip():
            try:
                lat = float(raw_lat)
                if not (INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX):
                    return None, {"row": row_id, "error": f"Latitude {lat} out of India bounds", "data": row}
            except ValueError:
                return None, {"row": row_id, "error": f"Invalid latitude format: {raw_lat}", "data": row}

        if raw_lon is not None and str(raw_lon).strip():
            try:
                lon = float(raw_lon)
                if not (INDIA_LON_MIN <= lon <= INDIA_LON_MAX):
                    return None, {"row": row_id, "error": f"Longitude {lon} out of India bounds", "data": row}
            except ValueError:
                return None, {"row": row_id, "error": f"Invalid longitude format: {raw_lon}", "data": row}

        # Observed timestamp
        observed_at = datetime.now(timezone.utc)
        raw_time = row.get("observed_at") or row.get("timestamp") or row.get("date")
        if raw_time:
            try:
                if isinstance(raw_time, str):
                    observed_at = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            except Exception:
                pass  # Fallback to now

        severity = None
        raw_sev = row.get("severity")
        if raw_sev:
            try:
                s_int = int(raw_sev)
                if 1 <= s_int <= 4:
                    severity = s_int
            except (ValueError, TypeError):
                pass

        event = CanonicalRawEvent(
            source_id=self.source_id,
            source_type="HISTORICAL_DATASET",
            external_id=row.get("id") or f"hist-{row_id}",
            text=str(text).strip(),
            observed_at=observed_at,
            latitude=lat,
            longitude=lon,
            city=row.get("city"),
            district=row.get("district"),
            state=row.get("state"),
            suggested_category=row.get("category"),
            severity=severity,
            raw_payload=row,
            is_demo=False,
        )
        return event, None
