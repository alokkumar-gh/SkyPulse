"""
SkyPulse Spatiotemporal Alignment & Cross-Source Merging Engine.
================================================================
Aligns disparate meteorological data sources (IMD, data.gov.in, ERA5, SkyPulse)
across spatial coordinates and temporal observation windows while preserving
provenance and cross-source evidence corroboration.
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from ml.schemas import TrainingRecord, LocationMethod

# Great-circle distance calculation
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class AlignmentEngine:
    """
    Coordinates spatial and temporal joins between ground observations and reanalysis data.
    """

    DEFAULT_TIME_WINDOW_HOURS = 3.0
    DEFAULT_SPATIAL_RADIUS_KM = 35.0

    @staticmethod
    def parse_datetime(dt_val: Any) -> Optional[datetime]:
        """Safely parses timestamp string or datetime object into UTC datetime."""
        if not dt_val:
            return None
        if isinstance(dt_val, datetime):
            return dt_val if dt_val.tzinfo else dt_val.replace(tzinfo=timezone.utc)
        if isinstance(dt_val, str):
            try:
                clean_str = dt_val.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean_str)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception:
                return None
        return None

    def align_timestamp(
        self,
        record_time: Any,
        window_hours: float = 3.0,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Aligns a continuous timestamp to the nearest discrete observation window (e.g. 3-hourly bucket).
        Returns (aligned_timestamp_iso, window_str).
        """
        dt = self.parse_datetime(record_time)
        if not dt:
            return None, None

        window_seconds = int(window_hours * 3600)
        epoch = dt.timestamp()
        bucket_epoch = round(epoch / window_seconds) * window_seconds
        aligned_dt = datetime.fromtimestamp(bucket_epoch, tz=timezone.utc)

        window_str = f"±{window_hours:.1f}h"
        return aligned_dt.isoformat(), window_str

    def join_era5_features(
        self,
        records_or_record: Any,
        era5_grid_points: Optional[List[Dict[str, Any]]] = None,
        era5_grid_data: Optional[List[Dict[str, Any]]] = None,
        max_distance_km: float = 50.0,
    ) -> Any:
        """
        Finds the nearest spatial-temporal ERA5 reanalysis grid point and attaches
        its normalized physical features under record.reanalysis_features.
        Supports single TrainingRecord or List[TrainingRecord].
        """
        pts = era5_grid_points if era5_grid_points is not None else (era5_grid_data or [])
        
        is_list = isinstance(records_or_record, list)
        records = records_or_record if is_list else [records_or_record]

        processed = []
        for record in records:
            lat, lon = record.latitude, record.longitude
            if lat is None or lon is None or not pts:
                processed.append(record)
                continue

            t_rec = self.parse_datetime(record.timestamp)
            best_point: Optional[Dict[str, Any]] = None
            min_dist = float("inf")

            for p in pts:
                p_lat = p.get("latitude")
                p_lon = p.get("longitude")
                if p_lat is None or p_lon is None:
                    continue

                dist = haversine_km(lat, lon, p_lat, p_lon)
                if dist > max_distance_km or dist >= min_dist:
                    continue

                # Check temporal match if timestamp present in ERA5 point
                p_time = self.parse_datetime(p.get("timestamp"))
                if t_rec and p_time:
                    delta_h = abs((t_rec - p_time).total_seconds()) / 3600.0
                    if delta_h > self.DEFAULT_TIME_WINDOW_HOURS:
                        continue

                min_dist = dist
                best_point = p

            if best_point:
                # If features are in raw format, extract them
                u = best_point.get("u_wind_10m") or best_point.get("10m_u_component_of_wind") or 0.0
                v = best_point.get("v_wind_10m") or best_point.get("10m_v_component_of_wind") or 0.0
                wind_speed = math.sqrt(u**2 + v**2)

                feats = dict(best_point.get("reanalysis_features") or {})
                if not feats:
                    feats = {
                        "era5_temperature_2m": best_point.get("temperature_2m"),
                        "era5_precipitation": best_point.get("total_precipitation"),
                        "era5_u_wind_10m": u,
                        "era5_v_wind_10m": v,
                        "era5_wind_speed_10m": round(wind_speed, 2),
                        "era5_surface_pressure": best_point.get("surface_pressure"),
                        "era5_dewpoint_2m": best_point.get("dewpoint_2m"),
                    }
                feats["era5_grid_distance_km"] = round(min_dist, 2)
                record.reanalysis_features = feats
                record.location_method = LocationMethod.NEAREST_ERA5_GRID.value
                if not record.aligned_timestamp:
                    aligned_ts, win = self.align_timestamp(record.timestamp, self.DEFAULT_TIME_WINDOW_HOURS)
                    record.aligned_timestamp = aligned_ts
                    record.alignment_window = win

            processed.append(record)

        return processed if is_list else processed[0]


alignment_engine = AlignmentEngine()

