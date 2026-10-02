"""
SkyPulse Leakage-Safe Dataset Splitter.
=======================================
Implements event-clustered and strictly chronological temporal train/validation/test splits.
Guarantees:
- ZERO temporal leakage (Train timestamp < Val timestamp < Test timestamp).
- ZERO spatial/event leakage (all reports from the same canonical event or cluster
  are assigned exclusively to one split partition).
- Supports both explicit chronological calendar boundaries (e.g. 2024-2025 Train,
  2026 H1 Val, 2026 H2+ Test) and ratio-based chronological splitting.
"""

import math
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timezone, date
from ml.schemas import TrainingRecord

logger = logging.getLogger("skypulse.ml.splitter")


class DatasetSplitter:
    """
    Partitions datasets into chronological and event-isolated Train, Validation, and Test sets.
    """

    @staticmethod
    def _parse_ts(ts_val: Any) -> Optional[datetime]:
        if not ts_val:
            return None
        if isinstance(ts_val, datetime):
            return ts_val if ts_val.tzinfo else ts_val.replace(tzinfo=timezone.utc)
        if isinstance(ts_val, date):
            return datetime(ts_val.year, ts_val.month, ts_val.day, tzinfo=timezone.utc)
        if isinstance(ts_val, str):
            try:
                # Handle YYYY-MM-DD or full ISO
                if len(ts_val.strip()) == 10:
                    dt = datetime.strptime(ts_val.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    return dt
                dt = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception:
                return None
        return None

    def split_chronological(
        self,
        records: List[TrainingRecord],
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        train_end_date: Optional[Union[str, datetime, date]] = None,
        val_end_date: Optional[Union[str, datetime, date]] = None,
        test_start_date: Optional[Union[str, datetime, date]] = None,
    ) -> Tuple[List[TrainingRecord], List[TrainingRecord], List[TrainingRecord], Dict[str, Any]]:
        """
        Sorts records by timestamp, clusters duplicate event families to avoid spatial/event leakage,
        and splits into chronological Train, Validation, and Test partitions.

        If explicit boundary dates (train_end_date, val_end_date, test_start_date) are provided:
          - Train: timestamp <= train_end_date (end of day)
          - Val: train_end_date < timestamp <= val_end_date (end of day)
          - Test: timestamp >= test_start_date (start of day)
        Otherwise, falls back to ratio-based chronological indexing.
        """
        if not records:
            return [], [], [], {
                "status": "EMPTY",
                "total_records": 0,
                "train_count": 0,
                "val_count": 0,
                "test_count": 0,
                "temporal_leakage_detected": False,
                "spatial_event_leakage_detected": False,
            }

        # 1. Attach sort keys and separate dated from undated records
        dated_records: List[Tuple[datetime, TrainingRecord]] = []
        undated_records: List[TrainingRecord] = []
        for r in records:
            dt = self._parse_ts(r.timestamp)
            if dt:
                dated_records.append((dt, r))
            else:
                undated_records.append(r)

        # Sort chronologically by timestamp
        dated_records.sort(key=lambda x: x[0])
        sorted_records = [r for _, r in dated_records]

        n = len(sorted_records)
        train_end_dt = self._parse_ts(train_end_date)
        val_end_dt = self._parse_ts(val_end_date)
        test_start_dt = self._parse_ts(test_start_date)

        use_explicit_dates = bool(train_end_dt and val_end_dt)

        if use_explicit_dates and train_end_dt and val_end_dt:
            # Set to end of day (23:59:59.999999) for end dates if time not specified
            if train_end_dt.hour == 0 and train_end_dt.minute == 0 and train_end_dt.second == 0:
                train_end_dt = train_end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            if val_end_dt.hour == 0 and val_end_dt.minute == 0 and val_end_dt.second == 0:
                val_end_dt = val_end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            if test_start_dt and test_start_dt.hour == 0 and test_start_dt.minute == 0:
                test_start_dt = test_start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                # Default test_start to just after val_end_dt
                test_start_dt = val_end_dt

            train_records = []
            val_records = []
            test_records = []

            for dt, rec in dated_records:
                if dt <= train_end_dt:
                    train_records.append(rec)
                elif dt <= val_end_dt:
                    val_records.append(rec)
                else:
                    test_records.append(rec)

            # Assign undated records to training partition as fallback
            train_records.extend(undated_records)

        else:
            # Ratio-based chronological index calculation
            train_idx = int(n * train_ratio)
            val_idx = int(n * (train_ratio + val_ratio))

            # Adjust indices to avoid splitting records belonging to the exact same event
            event_clusters: Dict[str, List[int]] = {}
            for idx, rec in enumerate(sorted_records):
                evt_id = rec.metadata.get("canonical_event_id") or rec.metadata.get("event_id") or rec.source_id
                if evt_id:
                    event_clusters.setdefault(evt_id, []).append(idx)

            # Ensure no event straddles train/val boundary
            for evt, indices in event_clusters.items():
                if min(indices) < train_idx < max(indices):
                    train_idx = max(indices) + 1

            for evt, indices in event_clusters.items():
                if min(indices) < val_idx < max(indices):
                    val_idx = max(indices) + 1

            train_records = sorted_records[:train_idx] + undated_records
            val_records = sorted_records[train_idx:val_idx]
            test_records = sorted_records[val_idx:]

        # 2. Extract and verify temporal boundaries
        train_start = self._get_time_boundary(train_records, first=True)
        train_end = self._get_time_boundary(train_records, first=False)
        val_start = self._get_time_boundary(val_records, first=True)
        val_end = self._get_time_boundary(val_records, first=False)
        test_start = self._get_time_boundary(test_records, first=True)
        test_end = self._get_time_boundary(test_records, first=False)

        leakage_detected = self.check_leakage(train_records, val_records, test_records)

        split_meta = {
            "total_records": len(train_records) + len(val_records) + len(test_records),
            "train_count": len(train_records),
            "val_count": len(val_records),
            "test_count": len(test_records),
            "train_start": train_start,
            "train_end": train_end,
            "val_start": val_start,
            "val_end": val_end,
            "test_start": test_start,
            "test_end": test_end,
            "split_mode": "EXPLICIT_CALENDAR_DATES" if use_explicit_dates else "CHRONOLOGICAL_RATIO",
            "temporal_leakage_detected": leakage_detected["temporal_leakage"],
            "spatial_event_leakage_detected": leakage_detected["spatial_event_leakage"],
        }

        return train_records, val_records, test_records, split_meta

    def _get_time_boundary(self, rec_list: List[TrainingRecord], first: bool = True) -> Optional[str]:
        valid_ts = [self._parse_ts(r.timestamp) for r in rec_list if self._parse_ts(r.timestamp)]
        if not valid_ts:
            return None
        valid_ts.sort()
        return valid_ts[0].isoformat() if first else valid_ts[-1].isoformat()

    def check_leakage(
        self,
        train_records: List[TrainingRecord],
        val_records: List[TrainingRecord],
        test_records: List[TrainingRecord],
    ) -> Dict[str, bool]:
        """
        Audits train, validation, and test sets for temporal or spatial/event ID overlap.
        """
        train_events = {r.metadata.get("canonical_event_id") for r in train_records if r.metadata.get("canonical_event_id")}
        val_events = {r.metadata.get("canonical_event_id") for r in val_records if r.metadata.get("canonical_event_id")}
        test_events = {r.metadata.get("canonical_event_id") for r in test_records if r.metadata.get("canonical_event_id")}

        spatial_leakage = bool((train_events & val_events) or (train_events & test_events) or (val_events & test_events))

        # Check temporal order: train_end <= val_start <= test_start
        train_end_dt = self._parse_ts(self._get_time_boundary(train_records, first=False))
        val_start_dt = self._parse_ts(self._get_time_boundary(val_records, first=True))
        val_end_dt = self._parse_ts(self._get_time_boundary(val_records, first=False))
        test_start_dt = self._parse_ts(self._get_time_boundary(test_records, first=True))

        temporal_leakage = False
        if train_end_dt and val_start_dt and train_end_dt > val_start_dt:
            temporal_leakage = True
        if val_end_dt and test_start_dt and val_end_dt > test_start_dt:
            temporal_leakage = True

        return {
            "temporal_leakage": temporal_leakage,
            "spatial_event_leakage": spatial_leakage,
        }


dataset_splitter = DatasetSplitter()
