"""
SkyPulse Dataset Quality, Validation, and Unit Normalization Engine.
===================================================================
Applies rigorous physical bounds checking, coordinate verification,
timestamp sanity checks, unit normalization, and error classification.
"""

import re
import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from ml.schemas import TrainingRecord, DataQualityStatus

# Physical Meteorologic Bounds (valid for Indian Climate)
BOUNDS = {
    "temperature_c": (-15.0, 55.0),      # Extreme Ladakh (-15°C) to Rajasthan (55°C)
    "rainfall_mm": (0.0, 1200.0),        # Daily precipitation max ~1000mm (Mawsynram record)
    "wind_speed_kmh": (0.0, 320.0),      # Super Cyclone max gusts ~300km/h
    "surface_pressure_hpa": (880.0, 1060.0), # Extreme cyclone eye to high pressure ridge
    "visibility_km": (0.0, 50.0),
    "latitude_india": (6.0, 38.0),       # Geographic bounds of India
    "longitude_india": (68.0, 98.0),
}


class DatasetQualityEngine:
    """
    Validates physical plausibility and normalizes units across raw records.
    """

    def __init__(self):
        self.rejected_records: List[Dict[str, Any]] = []

    @staticmethod
    def normalize_temperature(val: float, unit: str = "C") -> Optional[float]:
        """Normalizes temperature to Celsius (°C)."""
        if val is None or math.isnan(val):
            return None
        unit_clean = unit.upper().strip()
        if unit_clean in ("F", "FAHRENHEIT"):
            c = (val - 32.0) * 5.0 / 9.0
        elif unit_clean in ("K", "KELVIN"):
            c = val - 273.15
        else:
            c = val
        return round(c, 2)

    @staticmethod
    def normalize_rainfall(val: float, unit: str = "mm") -> Optional[float]:
        """Normalizes rainfall to millimeters (mm)."""
        if val is None or math.isnan(val) or val < 0:
            return None
        unit_clean = unit.lower().strip()
        if unit_clean in ("cm", "centimeter"):
            mm = val * 10.0
        elif unit_clean in ("m", "meter"):
            mm = val * 1000.0
        elif unit_clean in ("in", "inch", "inches"):
            mm = val * 25.4
        else:
            mm = val
        return round(mm, 2)

    @staticmethod
    def normalize_wind_speed(val: float, unit: str = "km/h") -> Optional[float]:
        """Normalizes wind speed to kilometers per hour (km/h)."""
        if val is None or math.isnan(val) or val < 0:
            return None
        unit_clean = unit.lower().strip()
        if unit_clean in ("m/s", "mps"):
            kmh = val * 3.6
        elif unit_clean in ("knots", "kt", "knot"):
            kmh = val * 1.852
        elif unit_clean in ("mph", "miles/h"):
            kmh = val * 1.60934
        else:
            kmh = val
        return round(kmh, 2)

    @staticmethod
    def normalize_pressure(val: float, unit: str = "hPa") -> Optional[float]:
        """Normalizes atmospheric pressure to hectopascals (hPa / mb)."""
        if val is None or math.isnan(val) or val <= 0:
            return None
        unit_clean = unit.lower().strip()
        if unit_clean in ("pa", "pascal"):
            hpa = val / 100.0
        elif unit_clean in ("bar", "bars"):
            hpa = val * 1000.0
        elif unit_clean in ("atm", "atmosphere"):
            hpa = val * 1013.25
        elif unit_clean in ("inhg", "in_hg"):
            hpa = val * 33.8639
        else:
            hpa = val
        return round(hpa, 2)

    def validate_record(self, record: TrainingRecord) -> Tuple[DataQualityStatus, List[str]]:
        """
        Runs comprehensive physical sanity, spatial, and temporal validation checks.
        Returns quality status (VALID, SUSPICIOUS, INVALID) and issue messages.
        """
        issues: List[str] = []
        status = DataQualityStatus.VALID

        # 1. Text checks
        text = (record.text or "").strip()
        if not text or len(text) < 5:
            issues.append("Text is missing or too short (< 5 chars)")
            return DataQualityStatus.INVALID, issues

        # 2. Coordinates checks
        lat, lon = record.latitude, record.longitude
        if lat is not None and lon is not None:
            if math.isnan(lat) or math.isnan(lon) or abs(lat) > 90.0 or abs(lon) > 180.0:
                issues.append(f"Invalid geographical coordinates: lat={lat}, lon={lon}")
                status = DataQualityStatus.INVALID
            elif not (BOUNDS["latitude_india"][0] <= lat <= BOUNDS["latitude_india"][1] and
                      BOUNDS["longitude_india"][0] <= lon <= BOUNDS["longitude_india"][1]):
                issues.append(f"Coordinates outside India bounding region: lat={lat}, lon={lon}")
                # Mark suspicious if just outside standard boundary
                status = DataQualityStatus.SUSPICIOUS if status != DataQualityStatus.INVALID else status

        # 3. Timestamp checks
        ts_str = record.timestamp
        if ts_str:
            try:
                if isinstance(ts_str, str):
                    ts_clean = ts_str.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(ts_clean)
                elif isinstance(ts_str, datetime):
                    dt = ts_str
                else:
                    dt = None

                if dt:
                    now = datetime.now(timezone.utc)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt > now:
                        issues.append(f"Future timestamp detected: {ts_str}")
                        status = DataQualityStatus.INVALID
                    elif dt.year < 1950:
                        issues.append(f"Ancient timestamp prior to 1950: {ts_str}")
                        status = DataQualityStatus.SUSPICIOUS
            except Exception as e:
                issues.append(f"Malformed timestamp string: {ts_str} ({e})")
                status = DataQualityStatus.INVALID
        else:
            issues.append("Missing timestamp")
            status = DataQualityStatus.SUSPICIOUS

        # 4. Severity checks
        if record.severity < 1 or record.severity > 4:
            issues.append(f"Severity out of range [1-4]: {record.severity}")
            status = DataQualityStatus.INVALID

        # 5. Numerical measurements check in metadata
        meta = record.metadata or {}
        if "temperature_c" in meta:
            t = meta["temperature_c"]
            if t is not None and (t < BOUNDS["temperature_c"][0] or t > BOUNDS["temperature_c"][1]):
                issues.append(f"Physically impossible temperature: {t} °C")
                status = DataQualityStatus.INVALID

        if "rainfall_mm" in meta:
            r = meta["rainfall_mm"]
            if r is not None and (r < BOUNDS["rainfall_mm"][0] or r > BOUNDS["rainfall_mm"][1]):
                issues.append(f"Physically impossible rainfall: {r} mm")
                status = DataQualityStatus.INVALID

        if "wind_speed_kmh" in meta:
            w = meta["wind_speed_kmh"]
            if w is not None and (w < BOUNDS["wind_speed_kmh"][0] or w > BOUNDS["wind_speed_kmh"][1]):
                issues.append(f"Physically impossible wind speed: {w} km/h")
                status = DataQualityStatus.INVALID

        return status, issues

    def validate_and_clean_record(self, raw: Dict[str, Any]) -> Tuple[DataQualityStatus, Optional[TrainingRecord], str]:
        """
        Validates raw payload, normalizes units, applies physical bounds checks,
        and constructs a canonical TrainingRecord if valid/suspicious.
        """
        text = (raw.get("text") or raw.get("raw_content") or raw.get("normalized_text") or "").strip()
        if not text or len(text) < 5:
            return DataQualityStatus.INVALID, None, "Text is missing or too short (< 5 chars)"

        lat = raw.get("latitude") or raw.get("location_lat")
        lon = raw.get("longitude") or raw.get("location_lon")

        # Coordinates check
        if lat is not None and (lat < -90.0 or lat > 90.0 or math.isnan(lat)):
            return DataQualityStatus.INVALID, None, f"Latitude out of valid range: {lat}"
        if lon is not None and (lon < -180.0 or lon > 180.0 or math.isnan(lon)):
            return DataQualityStatus.INVALID, None, f"Longitude out of valid range: {lon}"

        # Timestamp check
        ts_str = raw.get("timestamp") or raw.get("event_time") or raw.get("ingested_at")
        if ts_str:
            try:
                dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt > datetime.now(timezone.utc):
                    return DataQualityStatus.INVALID, None, f"Future timestamp detected: {ts_str}"
            except Exception as e:
                return DataQualityStatus.INVALID, None, f"Malformed timestamp: {ts_str} ({e})"

        # Unit Normalizations from raw metadata
        meta = dict(raw.get("metadata") or {})
        
        # Temperature normalization
        temp_val = meta.get("temperature_c") or meta.get("temp_c") or meta.get("temperature")
        if temp_val is not None:
            norm_temp = self.normalize_temperature(float(temp_val), "C")
            if norm_temp is not None and (norm_temp < BOUNDS["temperature_c"][0] or norm_temp > BOUNDS["temperature_c"][1]):
                return DataQualityStatus.INVALID, None, f"Impossible temperature: {norm_temp} °C"
            meta["temperature_c"] = norm_temp
        elif "temp_f" in meta:
            meta["temperature_c"] = self.normalize_temperature(float(meta["temp_f"]), "F")
        elif "temp_k" in meta:
            meta["temperature_c"] = self.normalize_temperature(float(meta["temp_k"]), "K")

        # Rainfall normalization
        rain_val = meta.get("rainfall_mm") or meta.get("rain_mm") or meta.get("precipitation_mm")
        if rain_val is not None:
            norm_rain = self.normalize_rainfall(float(rain_val), "mm")
            if norm_rain is not None and (norm_rain < BOUNDS["rainfall_mm"][0] or norm_rain > BOUNDS["rainfall_mm"][1]):
                return DataQualityStatus.INVALID, None, f"Impossible rainfall: {norm_rain} mm"
            meta["rainfall_mm"] = norm_rain
        elif "rainfall_cm" in meta:
            meta["rainfall_mm"] = self.normalize_rainfall(float(meta["rainfall_cm"]), "cm")
        elif "rainfall_in" in meta or "rainfall_inches" in meta:
            meta["rainfall_mm"] = self.normalize_rainfall(float(meta.get("rainfall_in") or meta.get("rainfall_inches")), "in")

        # Wind speed normalization
        wind_val = meta.get("wind_speed_kmh") or meta.get("wind_kmh")
        if wind_val is not None:
            norm_wind = self.normalize_wind_speed(float(wind_val), "km/h")
            if norm_wind is not None and (norm_wind < BOUNDS["wind_speed_kmh"][0] or norm_wind > BOUNDS["wind_speed_kmh"][1]):
                return DataQualityStatus.INVALID, None, f"Impossible wind speed: {norm_wind} km/h"
            meta["wind_speed_kmh"] = norm_wind
        elif "wind_mps" in meta or "wind_speed_mps" in meta:
            meta["wind_speed_kmh"] = self.normalize_wind_speed(float(meta.get("wind_mps") or meta.get("wind_speed_mps")), "m/s")
        elif "wind_knots" in meta or "wind_kt" in meta:
            meta["wind_speed_kmh"] = self.normalize_wind_speed(float(meta.get("wind_knots") or meta.get("wind_kt")), "knots")

        # Pressure normalization
        if "pressure_inhg" in meta:
            meta["pressure_hpa"] = self.normalize_pressure(float(meta["pressure_inhg"]), "inhg")
        elif "pressure_hpa" in meta:
            meta["pressure_hpa"] = self.normalize_pressure(float(meta["pressure_hpa"]), "hpa")

        # Visibility normalization
        if "visibility_m" in meta:
            meta["visibility_km"] = round(float(meta["visibility_m"]) / 1000.0, 2)
        elif "visibility_km" in meta:
            meta["visibility_km"] = round(float(meta["visibility_km"]), 2)

        # Build Record
        cat_str = (raw.get("category") or "UNKNOWN").upper().strip()
        try:
            from ml.schemas import WeatherEventCategory
            cat = WeatherEventCategory(cat_str) if cat_str in WeatherEventCategory._value2member_map_ else WeatherEventCategory.UNKNOWN
        except Exception:
            cat = None

        record = TrainingRecord(
            id=str(raw.get("id") or raw.get("source_id") or "rec"),
            text=text,
            category=cat,
            severity=int(raw.get("severity") or 2),
            timestamp=str(ts_str) if ts_str else None,
            latitude=lat,
            longitude=lon,
            source_type=raw.get("source_type") or "HISTORICAL",
            source_id=str(raw.get("source_id") or "src"),
            verified=bool(raw.get("verified", False)),
            verification_status=raw.get("verification_status") or ("VERIFIED" if raw.get("verified") else "UNVERIFIED"),
            label_source=raw.get("label_source"),
            label_confidence=float(raw.get("label_confidence") or 0.5),
            label_method=raw.get("label_method"),
            language=raw.get("language") or "en",
            location_method=raw.get("location_method"),
            conflict_flag=bool(raw.get("conflict_flag", False)),
            candidate_labels=raw.get("candidate_labels") or [],
            reanalysis_features=raw.get("reanalysis_features"),
            metadata=meta,
        )

        status, issues = self.validate_record(record)
        reason_str = "; ".join(issues) if issues else "VALID"
        return status, record, reason_str

    def audit_and_clean_dataset(self, raw_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Audits a collection of raw records, normalizes units, and separates valid and rejected records."""
        valid_records: List[TrainingRecord] = []
        suspicious_records: List[TrainingRecord] = []
        rejections: List[Dict[str, Any]] = []

        for idx, raw in enumerate(raw_records):
            status, rec, reason = self.validate_and_clean_record(raw)
            if status == DataQualityStatus.VALID and rec:
                valid_records.append(rec)
            elif status == DataQualityStatus.SUSPICIOUS and rec:
                suspicious_records.append(rec)
                valid_records.append(rec) # Keep suspicious in valid set with flag
            else:
                rejections.append({
                    "index": idx,
                    "reason": reason,
                    "raw_id": raw.get("id") or raw.get("source_id"),
                    "source_type": raw.get("source_type"),
                })

        quality_report = {
            "total_evaluated": len(raw_records),
            "valid_count": len(valid_records),
            "suspicious_count": len(suspicious_records),
            "rejected_count": len(rejections),
            "rejections": rejections[:100],  # Keep top 100 samples in report
        }

        return {
            "valid_records": valid_records,
            "quality_report": quality_report,
        }


quality_engine = DatasetQualityEngine()
dataset_quality_engine = quality_engine

