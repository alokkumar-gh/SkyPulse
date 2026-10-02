"""
SkyPulse Multi-Year ERA5 Reanalysis Dataset Acquisition Adapter.
================================================================
Fetches and processes historical & recent Copernicus Climate Data Store (CDS) ERA5
daily reanalysis statistics for India across multi-year date ranges (2024 through 2026+).

Key Capabilities:
- Multi-Year Monthly Chunking: Processes datasets in isolated monthly slices.
- Resumability & Caching: Caches processed monthly slices in compact Parquet format;
  validates chunk integrity and skips already processed months on session restarts.
- Auto-Cleaning: Deletes temporary raw NetCDF downloads immediately after processing.
- Latest-Date Discovery: Discovers and truncates requested date ranges to the latest
  actual CDS availability horizon.
- Zero Local Disk Impact: Integrates with configurable Google Drive paths for Colab workflows.
- Strict Weak-Label Semantics: Records weak meteorological threshold labels without
  claiming authoritative IMD ground-truth status.
"""

import os
import sys
import json
import math
import time
import shutil
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timezone, date, timedelta
from dataclasses import dataclass, field

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")

for p in [BASE_DIR, REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from ml.schemas import WeatherEventCategory, LocationMethod, TrainingRecord
except ImportError:
    from backend.ml.schemas import WeatherEventCategory, LocationMethod, TrainingRecord

logger = logging.getLogger("skypulse.ml.era5")

# Canonical India Bounding Box: [North, West, South, East]
INDIA_BOUNDING_BOX = [37.5, 68.0, 6.5, 97.5]

# Supported ERA5 Daily Variables
SUPPORTED_VARIABLES = [
    "2m_temperature",
    "2m_dewpoint_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "mean_sea_level_pressure",
    "total_precipitation",
    "surface_pressure",
]

# Estimated CDS ERA5 operational delay in days (ERA5T/daily statistics lag)
CDS_OPERATIONAL_DELAY_DAYS = 5


@dataclass
class ERA5MultiYearConfig:
    start_date: str = "2024-01-01"
    end_date: str = "2026-12-31"
    area: List[float] = field(default_factory=lambda: list(INDIA_BOUNDING_BOX))
    variables: List[str] = field(default_factory=lambda: list(SUPPORTED_VARIABLES))
    grid: List[float] = field(default_factory=lambda: [0.25, 0.25])
    cache_dir: str = "era5_cache"
    temp_dir: str = "tmp_raw_era5"
    auto_clean_temp: bool = True
    force_reprocess: bool = False
    latest_available: bool = True


class ERA5Adapter:
    """
    Adapter for multi-year Copernicus Climate Data Store (CDS) ERA5 reanalysis datasets.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        area: Optional[List[float]] = None,
        cache_dir: str = "era5_cache",
    ):
        self.api_url = (
            api_url
            or os.getenv("CDSAPI_URL")
            or os.getenv("CDS_API_URL")
            or "https://cds.climate.copernicus.eu/api"
        )
        self.api_key = api_key or os.getenv("CDSAPI_KEY") or os.getenv("CDS_API_KEY") or ""
        self.area = area or INDIA_BOUNDING_BOX
        self.cache_dir = cache_dir

        has_env_key = bool(self.api_key and self.api_key != "disabled")
        has_rc_file = os.path.exists(os.path.expanduser("~/.cdsapirc"))
        self.is_configured = has_env_key or has_rc_file

    def check_authentication(self) -> Dict[str, Any]:
        """
        Safely validates CDS API configuration and client initialization without downloading data.
        Never exposes secrets or credentials in return value.
        """
        if not self.is_configured:
            return {
                "status": "NOT_CONFIGURED",
                "message": "Neither CDSAPI_KEY environment variable nor ~/.cdsapirc found.",
                "authenticated": False,
            }
        try:
            import cdsapi
            if self.api_key:
                client = cdsapi.Client(url=self.api_url, key=self.api_key, quiet=True)
            else:
                client = cdsapi.Client(quiet=True)

            return {
                "status": "READY",
                "message": "Copernicus CDS API client initialized successfully.",
                "url": client.url,
                "authenticated": True,
            }
        except ImportError:
            return {
                "status": "ERROR",
                "message": "cdsapi python package is not installed.",
                "authenticated": False,
            }
        except Exception as e:
            err_msg = str(e)
            if self.api_key and self.api_key in err_msg:
                err_msg = err_msg.replace(self.api_key, "[REDACTED]")
            return {
                "status": "ERROR",
                "message": f"Authentication check failed: {err_msg}",
                "authenticated": False,
            }

    @staticmethod
    def discover_latest_available_date(
        requested_end_date: str,
        operational_delay_days: int = CDS_OPERATIONAL_DELAY_DAYS,
    ) -> Tuple[str, bool]:
        """
        Calculates the latest realistic ERA5 observation date available from CDS.
        If requested_end_date is in the future or within the CDS lag window, truncates safely.
        """
        try:
            req_dt = datetime.strptime(requested_end_date.strip()[:10], "%Y-%m-%d").date()
        except Exception:
            req_dt = date(2026, 12, 31)

        today_utc = datetime.now(timezone.utc).date()
        max_possible_available = today_utc - timedelta(days=operational_delay_days)

        if req_dt > max_possible_available:
            actual_end = max_possible_available.strftime("%Y-%m-%d")
            return actual_end, True
        return req_dt.strftime("%Y-%m-%d"), False

    @staticmethod
    def get_monthly_slices(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Splits a date range into calendar-aligned monthly slices:
        [{year: "2024", month: "01", start_day: 1, end_day: 31, days: ["01", ...]}, ...]
        """
        start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d").date()

        if start_dt > end_dt:
            return []

        slices = []
        curr = start_dt
        while curr <= end_dt:
            year_str = f"{curr.year:04d}"
            month_str = f"{curr.month:02d}"

            # Determine end of month
            if curr.month == 12:
                next_month = date(curr.year + 1, 1, 1)
            else:
                next_month = date(curr.year, curr.month + 1, 1)
            month_last_day = (next_month - timedelta(days=1)).day

            slice_start_day = curr.day
            slice_end_day = month_last_day if (curr.year < end_dt.year or curr.month < end_dt.month) else end_dt.day

            days_list = [f"{d:02d}" for d in range(slice_start_day, slice_end_day + 1)]

            slices.append({
                "year": year_str,
                "month": month_str,
                "start_day": slice_start_day,
                "end_day": slice_end_day,
                "days": days_list,
                "num_days": len(days_list),
            })

            # Advance to next month
            curr = next_month

        return slices

    @staticmethod
    def compute_wind_speed(u_ms: float, v_ms: float) -> Tuple[float, float]:
        """Calculates horizontal wind speed in m/s and km/h."""
        speed_ms = math.sqrt(u_ms * u_ms + v_ms * v_ms)
        speed_kmh = speed_ms * 3.6
        return round(speed_ms, 2), round(speed_kmh, 2)

    @staticmethod
    def kelvin_to_celsius(k: float) -> float:
        """Converts Kelvin to Celsius."""
        return round(k - 273.15, 2)

    @staticmethod
    def pascals_to_hpa(pa: float) -> float:
        """Converts Pascals to hPa."""
        return round(pa / 100.0, 2)

    @staticmethod
    def meters_to_mm(m: float) -> float:
        """Converts meters to millimeters."""
        return round(m * 1000.0, 2)

    @staticmethod
    def calculate_rh(temp_c: float, dew_c: float) -> float:
        """Calculates Relative Humidity (%) via Magnus-Tetens formula."""
        a, b = 17.625, 243.04
        alpha_t = (a * temp_c) / (b + temp_c)
        alpha_d = (a * dew_c) / (b + dew_c)
        rh = 100.0 * math.exp(alpha_d - alpha_t)
        return round(min(100.0, max(0.0, rh)), 2)

    def extract_reanalysis_features(
        self,
        raw_point: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Standardizes physical ERA5 reanalysis measurements into normalized SkyPulse units."""
        temp_k = raw_point.get("t2m") if "t2m" in raw_point else raw_point.get("2m_temperature")
        temp_c = self.kelvin_to_celsius(temp_k) if temp_k is not None else None

        dew_k = raw_point.get("d2m") if "d2m" in raw_point else raw_point.get("2m_dewpoint_temperature")
        dew_c = self.kelvin_to_celsius(dew_k) if dew_k is not None else None

        precip_m = raw_point.get("tp") if "tp" in raw_point else raw_point.get("total_precipitation")
        precip_mm = self.meters_to_mm(precip_m) if precip_m is not None else None

        u_wind = raw_point.get("u10") if "u10" in raw_point else raw_point.get("10m_u_component_of_wind", 0.0)
        v_wind = raw_point.get("v10") if "v10" in raw_point else raw_point.get("10m_v_component_of_wind", 0.0)
        u_val = float(u_wind) if u_wind is not None else 0.0
        v_val = float(v_wind) if v_wind is not None else 0.0
        speed_ms, speed_kmh = self.compute_wind_speed(u_val, v_val)

        press_pa = raw_point.get("sp") if "sp" in raw_point else (raw_point.get("surface_pressure") or raw_point.get("msl") or raw_point.get("mean_sea_level_pressure"))
        press_hpa = self.pascals_to_hpa(press_pa) if press_pa is not None else None

        rh = self.calculate_rh(temp_c, dew_c) if (temp_c is not None and dew_c is not None) else None

        return {
            "era5_temperature_2m_c": temp_c,
            "era5_dewpoint_2m_c": dew_c,
            "era5_relative_humidity_pct": rh,
            "era5_precipitation_mm": precip_mm,
            "era5_wind_speed_kmh": speed_kmh,
            "era5_wind_u_ms": round(u_val, 2),
            "era5_wind_v_ms": round(v_val, 2),
            "era5_surface_pressure_hpa": press_hpa,
            "era5_mslp_hpa": press_hpa,
        }

    def generate_weak_label_record(
        self,
        raw_point: Dict[str, Any],
        lat: float,
        lon: float,
        timestamp: str,
    ) -> Optional[TrainingRecord]:
        """Generates a conservative WEAK training sample from extreme meteorological conditions."""
        features = self.extract_reanalysis_features(raw_point)
        temp_c = features.get("era5_temperature_2m_c")
        precip_mm = features.get("era5_precipitation_mm")
        wind_kmh = features.get("era5_wind_speed_kmh")

        category: Optional[WeatherEventCategory] = None
        severity = 2
        confidence = 0.60
        text_desc = ""

        if precip_mm is not None and precip_mm >= 64.5:
            category = WeatherEventCategory.RAINFALL
            severity = 4 if precip_mm >= 120.0 else 3
            confidence = 0.70
            text_desc = f"ERA5 reanalysis indicates heavy precipitation exceeding {precip_mm:.1f} mm"
        elif temp_c is not None and temp_c >= 42.0:
            category = WeatherEventCategory.HEATWAVE
            severity = 4 if temp_c >= 45.0 else 3
            confidence = 0.65
            text_desc = f"ERA5 reanalysis records extreme maximum temperature of {temp_c:.1f} °C"
        elif wind_kmh is not None and wind_kmh >= 55.0:
            category = WeatherEventCategory.STRONG_WINDS
            severity = 3 if wind_kmh < 85.0 else 4
            confidence = 0.65
            text_desc = f"ERA5 reanalysis records strong surface wind speeds of {wind_kmh:.1f} km/h"

        if not category or not text_desc:
            return None

        return TrainingRecord(
            text=text_desc,
            category=category,
            severity=severity,
            timestamp=timestamp,
            latitude=round(lat, 4),
            longitude=round(lon, 4),
            source_type="ERA5_REANALYSIS",
            source_id=f"era5_{lat:.2f}_{lon:.2f}_{timestamp[:10]}",
            verified=False,
            verification_status="UNVERIFIED",
            label_source="ERA5_METEOROLOGICAL_REANALYSIS",
            label_confidence=confidence,
            label_method="WEAK_METEOROLOGICAL_THRESHOLD",
            language="en",
            location_method=LocationMethod.ERA5_GRID.value,
            conflict_flag=False,
            candidate_labels=[category.value],
            reanalysis_features=features,
            metadata={"reanalysis_dataset": "derived-era5-single-levels-daily-statistics", "bounding_box": self.area},
        )

    def get_chunk_paths(self, year: str, month: str, cache_dir: Optional[str] = None) -> Tuple[str, str]:
        """Returns the canonical (parquet_path, meta_path) for a given monthly chunk."""
        base_cache = cache_dir or self.cache_dir
        if os.path.basename(base_cache) == "monthly_chunks":
            chunk_dir = base_cache
        else:
            chunk_dir = os.path.join(base_cache, "monthly_chunks")
        parquet_path = os.path.join(chunk_dir, f"era5_{year}_{month}.parquet")
        meta_path = os.path.join(chunk_dir, f"era5_{year}_{month}.json")
        return parquet_path, meta_path

    def is_chunk_valid(self, year: str, month: str, cache_dir: Optional[str] = None) -> bool:
        """Validates whether a monthly cached chunk exists, is non-empty, and has valid manifest metadata."""
        base_cache = cache_dir or self.cache_dir
        p_path, m_path = self.get_chunk_paths(year, month, base_cache)

        # 1. Primary format: monthly_chunks/era5_YYYY_MM.parquet
        if os.path.exists(p_path) and os.path.exists(m_path) and os.path.getsize(p_path) >= 100:
            try:
                with open(m_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("status") == "COMPLETED" and meta.get("records_count", 0) > 0:
                    return True
            except Exception:
                pass

        # 2. Legacy tree format: YYYY/MM/processed.parquet
        tree_chunk = os.path.join(base_cache, year, month, "processed.parquet")
        tree_meta = os.path.join(base_cache, year, month, "manifest.json")
        if os.path.exists(tree_chunk) and os.path.exists(tree_meta) and os.path.getsize(tree_chunk) >= 100:
            try:
                with open(tree_meta, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("status") == "COMPLETED" and meta.get("records_count", 0) > 0:
                    return True
            except Exception:
                pass

        return False

    def fetch_and_process_monthly_chunk(
        self,
        year: str,
        month: str,
        days_list: List[str],
        config: ERA5MultiYearConfig,
    ) -> Dict[str, Any]:
        """Downloads, processes, normalizes, and caches a single monthly slice."""
        p_path, m_path = self.get_chunk_paths(year, month, config.cache_dir)
        os.makedirs(os.path.dirname(p_path), exist_ok=True)
        out_parquet = p_path
        meta_json = m_path

        # Check Resumability
        if not config.force_reprocess and self.is_chunk_valid(year, month, config.cache_dir):
            logger.info("Resuming: Month %s-%s already processed in cache. Skipping download.", year, month)
            if os.path.exists(meta_json):
                with open(meta_json, "r", encoding="utf-8") as f:
                    return json.load(f)
            legacy_meta = os.path.join(config.cache_dir, year, month, "manifest.json")
            if os.path.exists(legacy_meta):
                with open(legacy_meta, "r", encoding="utf-8") as f:
                    return json.load(f)

    @staticmethod
    def inspect_era5_file(file_path: str) -> Dict[str, Any]:
        """
        Inspects raw downloaded ERA5 file before xarray processing.
        Determines existence, size, magic signature bytes, MIME/container type, and potential error payloads.
        Never exposes secrets or credentials.
        """
        if not os.path.exists(file_path):
            return {
                "exists": False,
                "path": file_path,
                "size_bytes": 0,
                "size_mb": 0.0,
                "signature_hex": "",
                "signature_repr": "",
                "detected_format": "NOT_FOUND",
                "is_valid": False,
                "message": f"File does not exist: {file_path}",
            }

        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)

        if size_bytes == 0:
            return {
                "exists": True,
                "path": file_path,
                "size_bytes": 0,
                "size_mb": 0.0,
                "signature_hex": "",
                "signature_repr": "",
                "detected_format": "EMPTY",
                "is_valid": False,
                "message": "Downloaded file is 0 bytes (empty).",
            }

        with open(file_path, "rb") as f:
            header = f.read(64)

        sig_hex = header[:8].hex()
        sig_repr = repr(header[:16])

        # 1. HTML or JSON error payloads
        if header.startswith(b"<!DOC") or header.startswith(b"<html") or header.startswith(b"<HTML"):
            return {
                "exists": True,
                "path": file_path,
                "size_bytes": size_bytes,
                "size_mb": round(size_mb, 2),
                "signature_hex": sig_hex,
                "signature_repr": sig_repr,
                "detected_format": "HTML_ERROR",
                "is_valid": False,
                "message": "Downloaded file contains HTML response instead of binary NetCDF (CDS gateway/auth error).",
            }

        if header.strip().startswith(b"{") and (b"error" in header.lower() or b"message" in header.lower()):
            return {
                "exists": True,
                "path": file_path,
                "size_bytes": size_bytes,
                "size_mb": round(size_mb, 2),
                "signature_hex": sig_hex,
                "signature_repr": sig_repr,
                "detected_format": "JSON_ERROR",
                "is_valid": False,
                "message": "Downloaded file contains JSON error response from CDS API.",
            }

        # 2. ZIP Archive (standard CDS container packaging multi-variable/daily-statistic requests)
        if header.startswith(b"PK\x03\x04") or header.startswith(b"PK\x05\x06") or header.startswith(b"PK\x07\x08"):
            return {
                "exists": True,
                "path": file_path,
                "size_bytes": size_bytes,
                "size_mb": round(size_mb, 2),
                "signature_hex": sig_hex,
                "signature_repr": sig_repr,
                "detected_format": "ZIP_ARCHIVE",
                "is_valid": True,
                "message": "Downloaded file is a ZIP archive containing NetCDF files (CDS multi-variable package).",
            }

        # 3. HDF5 / NetCDF-4
        if header.startswith(b"\x89HDF\r\n\x1a\n"):
            return {
                "exists": True,
                "path": file_path,
                "size_bytes": size_bytes,
                "size_mb": round(size_mb, 2),
                "signature_hex": sig_hex,
                "signature_repr": sig_repr,
                "detected_format": "HDF5_NETCDF4",
                "is_valid": True,
                "message": "File has valid HDF5 / NetCDF-4 binary signature.",
            }

        # 4. Classic NetCDF (CDF-1, CDF-2, CDF-5)
        if header.startswith(b"CDF\x01") or header.startswith(b"CDF\x02") or header.startswith(b"CDF\x05"):
            return {
                "exists": True,
                "path": file_path,
                "size_bytes": size_bytes,
                "size_mb": round(size_mb, 2),
                "signature_hex": sig_hex,
                "signature_repr": sig_repr,
                "detected_format": "NETCDF_CLASSIC",
                "is_valid": True,
                "message": "File has valid Classic NetCDF (CDF) binary signature.",
            }

        # 5. GRIB format
        if header.startswith(b"GRIB"):
            return {
                "exists": True,
                "path": file_path,
                "size_bytes": size_bytes,
                "size_mb": round(size_mb, 2),
                "signature_hex": sig_hex,
                "signature_repr": sig_repr,
                "detected_format": "GRIB",
                "is_valid": True,
                "message": "File has GRIB binary signature.",
            }

        return {
            "exists": True,
            "path": file_path,
            "size_bytes": size_bytes,
            "size_mb": round(size_mb, 2),
            "signature_hex": sig_hex,
            "signature_repr": sig_repr,
            "detected_format": "UNKNOWN_BINARY",
            "is_valid": True,
            "message": f"Binary file with signature: {sig_hex}",
        }

    @classmethod
    def open_era5_dataset(
        cls,
        file_path: str,
        temp_extract_dir: Optional[str] = None,
    ) -> Tuple[Any, List[str]]:
        """
        Format-aware, robust opener for Copernicus CDS ERA5 files.
        1. Validates file existence, non-empty size, and absence of HTML/JSON error payloads.
        2. Identifies file type and handles zip extraction if CDS returned a ZIP container.
        3. Safely opens dataset trying controlled engine order: ['netcdf4', 'h5netcdf', 'scipy'].
        4. Validates presence of expected ERA5 physical variables.
        5. Returns (xarray.Dataset, cleanup_paths). Caller is responsible for dataset.close() & cleanup.
        """
        import zipfile
        import xarray as xr

        diagnostics = cls.inspect_era5_file(file_path)
        if not diagnostics["exists"]:
            raise FileNotFoundError(f"ERA5 file not found: {file_path}")

        if not diagnostics["is_valid"] or diagnostics["size_bytes"] == 0:
            raise ValueError(
                f"Downloaded CDS file is not a readable NetCDF file at '{file_path}' "
                f"(size: {diagnostics['size_bytes']} bytes, detected format: {diagnostics['detected_format']}). "
                f"Diagnostic: {diagnostics['message']}"
            )

        cleanup_paths: List[str] = []
        actual_nc_paths: List[str] = []

        # Handle ZIP container returned by CDS
        if diagnostics["detected_format"] == "ZIP_ARCHIVE" or zipfile.is_zipfile(file_path):
            extract_root = temp_extract_dir or os.path.join(
                os.path.dirname(file_path),
                f"extract_{os.path.splitext(os.path.basename(file_path))[0]}"
            )
            os.makedirs(extract_root, exist_ok=True)
            cleanup_paths.append(extract_root)

            with zipfile.ZipFile(file_path, "r") as zf:
                zf.extractall(extract_root)

            for root, _, files in os.walk(extract_root):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in [".nc", ".nc4", ".netcdf", ".cdf", ".grib", ".grb"] or f.startswith("data"):
                        actual_nc_paths.append(os.path.join(root, f))

            if not actual_nc_paths:
                for root, _, files in os.walk(extract_root):
                    for f in files:
                        actual_nc_paths.append(os.path.join(root, f))

            if not actual_nc_paths:
                raise ValueError(
                    f"Downloaded CDS ZIP archive at '{file_path}' did not contain any readable NetCDF/data files."
                )
        else:
            actual_nc_paths = [file_path]

        engines_to_try = ["netcdf4", "h5netcdf", "scipy"]
        opened_datasets: List[xr.Dataset] = []

        for sub_path in actual_nc_paths:
            ds = None
            engine_errors: List[str] = []
            for eng in engines_to_try:
                try:
                    ds = xr.open_dataset(sub_path, engine=eng)
                    break
                except Exception as e:
                    engine_errors.append(f"{eng}: {str(e)}")

            if ds is None:
                try:
                    ds = xr.open_dataset(sub_path)
                except Exception as e:
                    engine_errors.append(f"default: {str(e)}")

            if ds is None:
                raise ValueError(
                    f"Downloaded CDS file is not a readable NetCDF file at '{sub_path}' "
                    f"(size: {os.path.getsize(sub_path) if os.path.exists(sub_path) else 0} bytes, "
                    f"detected signature: {diagnostics['signature_hex']}). "
                    f"Engines attempted: {engine_errors}"
                )
            opened_datasets.append(ds)

        if len(opened_datasets) == 1:
            merged_ds = opened_datasets[0]
        else:
            try:
                merged_ds = xr.merge(opened_datasets, compat="override")
            except Exception:
                try:
                    merged_ds = xr.combine_by_coords(opened_datasets, combine_attrs="override")
                except Exception:
                    merged_ds = opened_datasets[0]

        # Validate expected ERA5 variables
        available_vars = list(merged_ds.data_vars.keys()) + list(merged_ds.coords.keys())
        available_vars_lower = [v.lower() for v in available_vars]

        has_temp = any(v in available_vars_lower for v in ["t2m", "2m_temperature", "temperature_2m", "t"])
        has_precip = any(v in available_vars_lower for v in ["tp", "total_precipitation", "precipitation", "precip"])
        has_u = any(v in available_vars_lower for v in ["u10", "10m_u_component_of_wind", "u_component_of_wind_10m", "u"])
        has_v = any(v in available_vars_lower for v in ["v10", "10m_v_component_of_wind", "v_component_of_wind_10m", "v"])
        has_press = any(v in available_vars_lower for v in ["msl", "mean_sea_level_pressure", "sp", "surface_pressure", "pressure"])
        has_dew = any(v in available_vars_lower for v in ["d2m", "2m_dewpoint_temperature", "dewpoint_temperature_2m", "d"])

        missing = []
        if not has_temp:
            missing.append("2m_temperature (t2m)")
        if not has_precip:
            missing.append("total_precipitation (tp)")
        if not has_u:
            missing.append("10m_u_component_of_wind (u10)")
        if not has_v:
            missing.append("10m_v_component_of_wind (v10)")
        if not has_press:
            missing.append("mean_sea_level_pressure (msl) / surface_pressure (sp)")
        if not has_dew:
            missing.append("2m_dewpoint_temperature (d2m)")

        if missing:
            logger.warning(
                "ERA5 NetCDF opened successfully, but some expected variables were missing: %s. Available in dataset: %s",
                missing,
                available_vars,
            )

        return merged_ds, cleanup_paths

    def fetch_and_process_monthly_chunk(
        self,
        year: str,
        month: str,
        days_list: List[str],
        config: ERA5MultiYearConfig,
    ) -> Dict[str, Any]:
        """Downloads, processes, normalizes, and caches a single monthly slice."""
        p_path, m_path = self.get_chunk_paths(year, month, config.cache_dir)
        os.makedirs(os.path.dirname(p_path), exist_ok=True)
        out_parquet = p_path
        meta_json = m_path

        # Check Resumability
        if not config.force_reprocess and self.is_chunk_valid(year, month, config.cache_dir):
            logger.info("Resuming: Month %s-%s already processed in cache. Skipping download.", year, month)
            if os.path.exists(meta_json):
                with open(meta_json, "r", encoding="utf-8") as f:
                    return json.load(f)
            legacy_meta = os.path.join(config.cache_dir, year, month, "manifest.json")
            if os.path.exists(legacy_meta):
                with open(legacy_meta, "r", encoding="utf-8") as f:
                    return json.load(f)

        if not self.is_configured:
            logger.warning("CDS API credentials not configured. Cannot download ERA5 %s-%s.", year, month)
            return {
                "status": "NOT_CONFIGURED",
                "year": year,
                "month": month,
                "records_count": 0,
            }

        os.makedirs(config.temp_dir, exist_ok=True)
        raw_nc_path = os.path.join(config.temp_dir, f"raw_era5_{year}_{month}.nc")
        t_start = time.time()

        try:
            import cdsapi
            client = cdsapi.Client(url=self.api_url, key=self.api_key, quiet=True) if self.api_key else cdsapi.Client(quiet=True)

            request_payload = {
                "product_type": "reanalysis",
                "variable": config.variables,
                "year": year,
                "month": month,
                "day": days_list,
                "daily_statistic": "daily_mean",
                "time_zone": "utc+05:30",
                "frequency": "1_hourly",
                "area": config.area,
                "format": "netcdf",
            }

            logger.info("Downloading ERA5 %s-%s (%d days) to %s...", year, month, len(days_list), raw_nc_path)
            try:
                client.retrieve("derived-era5-single-levels-daily-statistics", request_payload, raw_nc_path)
            except Exception as de:
                logger.info("Retrying with reanalysis-era5-single-levels fallback: %s", de)
                alt_payload = {
                    "product_type": "reanalysis",
                    "format": "netcdf",
                    "variable": config.variables,
                    "year": year,
                    "month": month,
                    "day": days_list,
                    "time": ["00:00", "06:00", "12:00", "18:00"],
                    "area": config.area,
                }
                client.retrieve("reanalysis-era5-single-levels", alt_payload, raw_nc_path)

            # 1. Download Validation Immediately After Retrieval
            diag = self.inspect_era5_file(raw_nc_path)
            if not diag["exists"] or not diag["is_valid"] or diag["size_bytes"] == 0:
                err_detail = diag.get("message", "Invalid downloaded file")
                logger.error(
                    "Download validation failed for ERA5 %s-%s at %s: %s (Format: %s, Sig: %s, Size: %d bytes)",
                    year, month, raw_nc_path, err_detail, diag.get("detected_format"), diag.get("signature_hex"), diag.get("size_bytes")
                )
                return {
                    "year": year,
                    "month": month,
                    "status": f"FAILED: {err_detail}",
                    "records_count": 0,
                    "diagnostics": diag,
                }

            raw_size_mb = diag["size_mb"]
            logger.info("Raw download validated: %.2f MB (Format: %s, Signature: %s)", raw_size_mb, diag["detected_format"], diag["signature_hex"])

            # 2. Process into standardized TrainingRecords / Dataframe
            records, rejected_count = self._process_netcdf_file(raw_nc_path, year, month)

            # 3. Save compact Parquet
            import pandas as pd
            records_data = [r.model_dump() for r in records]
            df = pd.DataFrame(records_data)
            df.to_parquet(out_parquet, engine="pyarrow", compression="snappy", index=False)
            parquet_size_mb = os.path.getsize(out_parquet) / (1024 * 1024)

            # 4. Calculate SHA256
            sha256 = hashlib.sha256()
            with open(out_parquet, "rb") as f:
                while chunk := f.read(65536):
                    sha256.update(chunk)
            chunk_hash = sha256.hexdigest()

            elapsed = time.time() - t_start
            summary = {
                "year": year,
                "month": month,
                "status": "COMPLETED",
                "records_count": len(records),
                "rejected_count": rejected_count,
                "raw_size_mb": round(raw_size_mb, 2),
                "parquet_size_mb": round(parquet_size_mb, 2),
                "sha256": chunk_hash,
                "processing_time_sec": round(elapsed, 1),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "variables": config.variables,
                "area": config.area,
            }

            with open(meta_json, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)

            # 5. Auto-clean temporary raw NetCDF on success
            if config.auto_clean_temp and os.path.exists(raw_nc_path):
                os.remove(raw_nc_path)
                logger.info("Cleaned temporary raw file: %s (reclaimed %.2f MB)", raw_nc_path, raw_size_mb)

            logger.info("Month %s-%s finalized: %d records -> %.2f MB Parquet (%.1fs)", year, month, len(records), parquet_size_mb, elapsed)
            return summary

        except Exception as e:
            logger.error("Failed processing ERA5 month %s-%s: %s", year, month, e)
            # DO NOT delete failed raw file until diagnostics are captured
            return {
                "year": year,
                "month": month,
                "status": f"FAILED: {str(e)}",
                "records_count": 0,
            }

    def _process_netcdf_file(
        self,
        nc_file_path: str,
        year: str,
        month: str,
    ) -> Tuple[List[TrainingRecord], int]:
        """Parses NetCDF file into normalized TrainingRecord models with quality bounds validation."""
        import pandas as pd

        ds, cleanup_paths = self.open_era5_dataset(nc_file_path)
        try:
            df = ds.to_dataframe().reset_index()
        finally:
            ds.close()
            for cp in cleanup_paths:
                if os.path.exists(cp):
                    shutil.rmtree(cp, ignore_errors=True)

        cols_lower = {c.lower(): c for c in df.columns}

        def get_col(*candidates: str) -> Optional[str]:
            for cand in candidates:
                if cand.lower() in cols_lower:
                    return cols_lower[cand.lower()]
            return None

        t2m_col = get_col("t2m", "2m_temperature", "temperature_2m", "t")
        d2m_col = get_col("d2m", "2m_dewpoint_temperature", "dewpoint_temperature_2m", "d")
        tp_col = get_col("tp", "total_precipitation", "precipitation", "precip")
        u10_col = get_col("u10", "10m_u_component_of_wind", "u_component_of_wind_10m", "u")
        v10_col = get_col("v10", "10m_v_component_of_wind", "v_component_of_wind_10m", "v")
        mslp_col = get_col("msl", "mean_sea_level_pressure", "sp", "surface_pressure", "pressure")

        lat_col = get_col("latitude", "lat") or "latitude"
        lon_col = get_col("longitude", "lon") or "longitude"
        time_col = get_col("time", "valid_time", "date") or "time"

        records: List[TrainingRecord] = []
        rejected_count = 0

        for _, r in df.iterrows():
            lat = float(r[lat_col])
            lon = float(r[lon_col])
            ts = pd.to_datetime(r[time_col]).strftime("%Y-%m-%d")

            if lat < 6.5 or lat > 38.5 or lon < 66.5 or lon > 100.0:
                rejected_count += 1
                continue

            raw_t = r.get(t2m_col)
            temp_c = round(float(raw_t) - 273.15, 2) if pd.notnull(raw_t) else None

            raw_d = r.get(d2m_col)
            dew_c = round(float(raw_d) - 273.15, 2) if pd.notnull(raw_d) else None

            raw_p = r.get(tp_col)
            precip_mm = round(float(raw_p) * 1000.0, 2) if pd.notnull(raw_p) else 0.0
            precip_mm = max(0.0, precip_mm)

            u_wind = float(r.get(u10_col, 0.0)) if pd.notnull(r.get(u10_col)) else 0.0
            v_wind = float(r.get(v10_col, 0.0)) if pd.notnull(r.get(v10_col)) else 0.0
            wind_spd_kmh = round(math.sqrt(u_wind**2 + v_wind**2) * 3.6, 2)
            wind_dir_deg = round((math.degrees(math.atan2(-u_wind, -v_wind)) + 360.0) % 360.0, 1)

            raw_msl = r.get(mslp_col)
            mslp_hpa = round(float(raw_msl) / 100.0, 2) if pd.notnull(raw_msl) else None

            if temp_c is not None and (temp_c < -40.0 or temp_c > 60.0):
                rejected_count += 1
                continue
            if dew_c is not None and temp_c is not None and dew_c > (temp_c + 2.0):
                rejected_count += 1
                continue

            rh = self.calculate_rh(temp_c, dew_c) if (temp_c is not None and dew_c is not None) else None

            category = WeatherEventCategory.UNKNOWN
            severity = 1
            label_confidence = 0.50
            text_desc = f"ERA5 meteorological observation at {lat:.2f}N, {lon:.2f}E: temp={temp_c}°C, rain={precip_mm}mm, wind={wind_spd_kmh}km/h"

            if precip_mm >= 64.5:
                category = WeatherEventCategory.RAINFALL
                severity = 4 if precip_mm >= 120.0 else 3
                label_confidence = 0.70
                text_desc = f"ERA5 reanalysis records heavy rainfall exceeding {precip_mm:.1f} mm/day"
            elif temp_c is not None and temp_c >= 42.0:
                category = WeatherEventCategory.HEATWAVE
                severity = 4 if temp_c >= 45.0 else 3
                label_confidence = 0.65
                text_desc = f"ERA5 reanalysis records extreme high temperature of {temp_c:.1f} °C"
            elif wind_spd_kmh >= 55.0:
                category = WeatherEventCategory.STRONG_WINDS
                severity = 3 if wind_spd_kmh < 85.0 else 4
                label_confidence = 0.65
                text_desc = f"ERA5 reanalysis records strong surface winds of {wind_spd_kmh:.1f} km/h"

            rec = TrainingRecord(
                text=text_desc,
                category=category,
                severity=severity,
                timestamp=f"{ts}T00:00:00Z",
                latitude=round(lat, 4),
                longitude=round(lon, 4),
                source_type="ERA5_REANALYSIS",
                source_id=f"era5_{lat:.2f}_{lon:.2f}_{ts}",
                verified=False,
                verification_status="UNVERIFIED",
                label_source="ERA5_METEOROLOGICAL_REANALYSIS",
                label_confidence=label_confidence,
                label_method="WEAK_METEOROLOGICAL_THRESHOLD",
                language="en",
                location_method=LocationMethod.ERA5_GRID.value,
                conflict_flag=False,
                candidate_labels=[category.value],
                reanalysis_features={
                    "era5_temperature_2m_c": temp_c,
                    "era5_dewpoint_2m_c": dew_c,
                    "era5_relative_humidity_pct": rh,
                    "era5_precipitation_mm": precip_mm,
                    "era5_wind_speed_kmh": wind_spd_kmh,
                    "era5_wind_direction_deg": wind_dir_deg,
                    "era5_wind_u_ms": round(u_wind, 2),
                    "era5_wind_v_ms": round(v_wind, 2),
                    "era5_mslp_hpa": mslp_hpa,
                },
                metadata={
                    "reanalysis_dataset": "derived-era5-single-levels-daily-statistics",
                    "year": year,
                    "month": month,
                    "label_type": "WEAK" if category != WeatherEventCategory.UNKNOWN else "UNLABELED",
                },
            )
            records.append(rec)

        return records, rejected_count

    def process_era5_training_records(
        self,
        config: Union[ERA5MultiYearConfig, Any],
    ) -> List[TrainingRecord]:
        """Executes multi-year monthly chunk processing across the configured date range."""
        if not isinstance(config, ERA5MultiYearConfig):
            config = ERA5MultiYearConfig(
                start_date=getattr(config, "start_date", "2024-01-01"),
                end_date=getattr(config, "end_date", "2024-01-07"),
                area=getattr(config, "area", INDIA_BOUNDING_BOX),
                variables=getattr(config, "variables", SUPPORTED_VARIABLES),
                grid=getattr(config, "grid", [0.25, 0.25]),
            )

        actual_end_date, is_truncated = self.discover_latest_available_date(config.end_date)
        if is_truncated and config.latest_available:
            logger.info("Truncated requested end date '%s' to latest available CDS date '%s'.", config.end_date, actual_end_date)

        monthly_slices = self.get_monthly_slices(config.start_date, actual_end_date)
        if not monthly_slices:
            logger.warning("No valid monthly slices for range %s to %s", config.start_date, actual_end_date)
            return []

        all_records: List[TrainingRecord] = []
        for s in monthly_slices:
            chunk_summary = self.fetch_and_process_monthly_chunk(
                year=s["year"],
                month=s["month"],
                days_list=s["days"],
                config=config,
            )
            if chunk_summary.get("status") == "COMPLETED":
                p_path, _ = self.get_chunk_paths(s["year"], s["month"], config.cache_dir)
                if not os.path.exists(p_path):
                    p_path = os.path.join(config.cache_dir, s["year"], s["month"], "processed.parquet")
                if os.path.exists(p_path):
                    import pandas as pd
                    df = pd.read_parquet(p_path)
                    for _, row in df.iterrows():
                        all_records.append(TrainingRecord.model_validate(dict(row)))

        return all_records


era5_adapter = ERA5Adapter()
ERA5Config = ERA5MultiYearConfig
