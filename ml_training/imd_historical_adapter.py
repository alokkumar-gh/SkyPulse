"""
SkyPulse IMD Historical Climate Research & Services (CRS) Gridded Dataset Adapter.
==================================================================================
Parses official India Meteorological Department (IMD) Pune Climate Research & Services
daily gridded rainfall (0.25° x 0.25°) and daily gridded temperature (0.5° x 0.5° / 1.0° x 1.0°)
datasets into normalized SkyPulse TrainingRecord envelopes with complete government provenance.

Source Attribution:
  - Source Type: IMD_HISTORICAL_CRS
  - Agency: India Meteorological Department (IMD) - Climate Research & Services (CRS), Pune
  - Bounding Box: India [6.5°N - 38.5°N, 66.5°E - 100.0°E]
  - Provenance: Government Gridded Climate Observation
"""

import os
import sys
import glob
import math
import logging
import argparse
from typing import Dict, Any, List, Optional, Tuple, Generator
from datetime import datetime, timezone, date

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

from ml_training.quality import quality_engine, DataQualityStatus
from ml_training.labeling import labeling_engine

logger = logging.getLogger("skypulse.ml.imd_historical")

# Official IMD India Domain Bounding Box
IMD_INDIA_BOUNDS = {
    "lat_min": 6.5,
    "lat_max": 38.5,
    "lon_min": 66.5,
    "lon_max": 100.0,
}

# Recognized variable names in IMD NetCDF products
RAINFALL_VAR_NAMES = ["rf", "rainfall", "rain", "RAINFALL", "precip", "precipitation"]
TMAX_VAR_NAMES = ["tmax", "TMAX", "temp_max", "max_temp", "t_max"]
TMIN_VAR_NAMES = ["tmin", "TMIN", "temp_min", "min_temp", "t_min"]
TEMP_VAR_NAMES = ["temp", "temperature", "TEMPREATURE", "t2m"]

LAT_COORD_NAMES = ["lat", "latitude", "LATITUDE", "LAT", "y"]
LON_COORD_NAMES = ["lon", "longitude", "LONGITUDE", "LON", "long", "x"]
TIME_COORD_NAMES = ["time", "TIME", "date", "DATE", "day", "t"]


class IMDHistoricalCRSAdapter:
    """
    Adapter for official IMD Pune Climate Research & Services (CRS) gridded historical datasets.
    """

    def __init__(
        self,
        data_dir: Optional[str] = None,
        bounds: Optional[Dict[str, float]] = None,
    ):
        self.data_dir = data_dir or os.getenv("IMD_CRS_DATA_DIR", os.path.join(REPO_ROOT, "data", "imd_crs"))
        self.bounds = bounds or IMD_INDIA_BOUNDS

    def inspect_file(self, file_path: str) -> Dict[str, Any]:
        """
        Inspects an IMD NetCDF/Binary file and returns structural metadata,
        dimensions, variables, coordinate bounds, date span, and SkyPulse compatibility.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"IMD CRS file not found: {file_path}")

        info: Dict[str, Any] = {
            "file_path": os.path.abspath(file_path),
            "file_name": os.path.basename(file_path),
            "file_size_mb": round(os.path.getsize(file_path) / (1024 * 1024), 2),
            "format": "NetCDF",
            "compatible": False,
            "dimensions": {},
            "variables": {},
            "lat_range": None,
            "lon_range": None,
            "date_range": None,
            "estimated_record_count": 0,
            "errors": [],
        }

        try:
            import xarray as xr
            import numpy as np

            ds = xr.open_dataset(file_path)

            # Dimensions
            for dim_name, dim_size in ds.sizes.items():
                info["dimensions"][str(dim_name)] = int(dim_size)

            # Variables
            detected_met_var = None
            for var_name, data_var in ds.data_vars.items():
                attrs = dict(data_var.attrs)
                info["variables"][str(var_name)] = {
                    "shape": [int(s) for s in data_var.shape],
                    "dtype": str(data_var.dtype),
                    "units": attrs.get("units", "unknown"),
                    "long_name": attrs.get("long_name", str(var_name)),
                }
                v_lower = str(var_name).lower()
                if v_lower in RAINFALL_VAR_NAMES or v_lower in TMAX_VAR_NAMES or v_lower in TEMP_VAR_NAMES:
                    detected_met_var = str(var_name)

            # Coordinates
            lat_coord, lon_coord, time_coord = self._detect_coords(ds)

            if lat_coord is not None:
                lats = ds[lat_coord].values
                info["lat_range"] = [float(np.nanmin(lats)), float(np.nanmax(lats))]

            if lon_coord is not None:
                lons = ds[lon_coord].values
                info["lon_range"] = [float(np.nanmin(lons)), float(np.nanmax(lons))]

            if time_coord is not None:
                times = ds[time_coord].values
                if len(times) > 0:
                    t_min = str(np.nanmin(times))[:10]
                    t_max = str(np.nanmax(times))[:10]
                    info["date_range"] = {"start": t_min, "end": t_max}

            # Compatibility Check
            if lat_coord and lon_coord and time_coord and detected_met_var:
                info["compatible"] = True
                info["primary_variable"] = detected_met_var
                info["estimated_record_count"] = int(
                    ds.sizes.get(time_coord, 0) * ds.sizes.get(lat_coord, 0) * ds.sizes.get(lon_coord, 0)
                )
            else:
                missing = []
                if not lat_coord: missing.append("Latitude coordinate")
                if not lon_coord: missing.append("Longitude coordinate")
                if not time_coord: missing.append("Time coordinate")
                if not detected_met_var: missing.append("Meteorological data variable (rf/rainfall/tmax)")
                info["errors"].append(f"Missing required attributes: {', '.join(missing)}")

            ds.close()

        except Exception as e:
            info["format"] = "Unknown / Non-NetCDF"
            info["errors"].append(str(e))

        return info

    def extract(
        self,
        files: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_records: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Discovers and processes local IMD CRS files for the requested date range.
        Returns canonical TrainingRecord envelopes.
        """
        target_files = files
        if not target_files:
            if os.path.exists(self.data_dir):
                target_files = glob.glob(os.path.join(self.data_dir, "*.nc")) + glob.glob(os.path.join(self.data_dir, "*.NC"))
            else:
                target_files = []

        if not target_files:
            logger.info("No local IMD CRS files found in data directory: %s", self.data_dir)
            return {
                "status": "NOT_CONFIGURED",
                "message": f"No IMD CRS NetCDF (.nc) files found in {self.data_dir}. Place official IMD Pune files to ingest.",
                "records": [],
            }

        all_records: List[TrainingRecord] = []
        errors = []

        for fp in target_files:
            try:
                recs = self.parse_netcdf(
                    file_path=fp,
                    start_date=start_date,
                    end_date=end_date,
                    max_records=max_records,
                )
                all_records.extend(recs)
                logger.info("Ingested %d valid records from IMD CRS file: %s", len(recs), os.path.basename(fp))
            except Exception as e:
                err_msg = f"Failed to parse IMD CRS file {os.path.basename(fp)}: {e}"
                logger.error(err_msg)
                errors.append(err_msg)

        status = "AVAILABLE" if all_records else ("ERROR" if errors else "NO_DATA")
        return {
            "status": status,
            "file_count": len(target_files),
            "record_count": len(all_records),
            "records": [r.model_dump() for r in all_records],
            "errors": errors,
        }

    def parse_netcdf(
        self,
        file_path: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_records: Optional[int] = None,
        threshold_filter_only: bool = True,
    ) -> List[TrainingRecord]:
        """
        Parses an IMD NetCDF file using chunked time-slices, applies spatial India filtering,
        normalizes units, and converts meteorological observations to TrainingRecords.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            import xarray as xr
            import numpy as np
            import pandas as pd
        except ImportError:
            raise RuntimeError("xarray, netCDF4, and pandas are required for IMD NetCDF parsing.")

        ds = xr.open_dataset(file_path)

        lat_coord, lon_coord, time_coord = self._detect_coords(ds)
        if not lat_coord or not lon_coord or not time_coord:
            ds.close()
            raise ValueError(f"Incomplete coordinates in {file_path}: lat={lat_coord}, lon={lon_coord}, time={time_coord}")

        # Detect primary meteorological variable
        met_var = None
        var_type = "UNKNOWN"
        for v in ds.data_vars:
            v_low = str(v).lower()
            if v_low in RAINFALL_VAR_NAMES:
                met_var = str(v)
                var_type = "RAINFALL"
                break
            elif v_low in TMAX_VAR_NAMES:
                met_var = str(v)
                var_type = "TMAX"
                break
            elif v_low in TMIN_VAR_NAMES:
                met_var = str(v)
                var_type = "TMIN"
                break
            elif v_low in TEMP_VAR_NAMES:
                met_var = str(v)
                var_type = "TEMPERATURE"
                break

        if not met_var:
            ds.close()
            raise ValueError(f"No recognizable meteorological variable (rf/tmax/tmin/temp) in {file_path}")

        # Crop to India Bounding Box spatially
        lat_slice = slice(self.bounds["lat_min"], self.bounds["lat_max"])
        # Handle ascending vs descending latitude
        lat_vals = ds[lat_coord].values
        if len(lat_vals) > 1 and lat_vals[0] > lat_vals[-1]:
            lat_slice = slice(self.bounds["lat_max"], self.bounds["lat_min"])

        lon_slice = slice(self.bounds["lon_min"], self.bounds["lon_max"])
        ds_cropped = ds.sel({lat_coord: lat_slice, lon_coord: lon_slice})

        # Filter by date range if provided
        if start_date:
            try:
                ds_cropped = ds_cropped.sel({time_coord: slice(start_date, end_date or start_date)})
            except Exception as te:
                logger.warning("Time slicing with string failed, attempting datetime conversion: %s", te)

        records: List[TrainingRecord] = []
        data_arr = ds_cropped[met_var]
        units_attr = str(data_arr.attrs.get("units", "")).lower()

        # Iterate lazily over time dimension to maintain low memory footprint
        time_vals = ds_cropped[time_coord].values
        file_name = os.path.basename(file_path)

        for t_idx, t_val in enumerate(time_vals):
            if max_records and len(records) >= max_records:
                break

            # Format timestamp
            if isinstance(t_val, (np.datetime64, pd.Timestamp)):
                dt_str = pd.to_datetime(t_val).strftime("%Y-%m-%d")
                ts_iso = pd.to_datetime(t_val).tz_localize("UTC").isoformat()
            else:
                dt_str = str(t_val)[:10]
                ts_iso = f"{dt_str}T00:00:00+00:00"

            # Filter date bounds explicitly
            if start_date and dt_str < start_date:
                continue
            if end_date and dt_str > end_date:
                continue

            slice_2d = data_arr.isel({time_coord: t_idx}).values
            lats = ds_cropped[lat_coord].values
            lons = ds_cropped[lon_coord].values

            for i, lat in enumerate(lats):
                for j, lon in enumerate(lons):
                    if max_records and len(records) >= max_records:
                        break

                    val = slice_2d[i, j]
                    if np.isnan(val) or val is None or val in (-999.0, 999.0, -9999.0):
                        continue

                    val_float = float(val)

                    # Build Training Record
                    rec = self._build_record_from_grid_point(
                        lat=float(lat),
                        lon=float(lon),
                        date_str=dt_str,
                        timestamp_iso=ts_iso,
                        var_type=var_type,
                        var_name=met_var,
                        value=val_float,
                        units=units_attr,
                        file_name=file_name,
                        threshold_filter_only=threshold_filter_only,
                    )

                    if rec is not None:
                        # Quality check
                        status, _ = quality_engine.validate_record(rec)
                        if status != DataQualityStatus.INVALID:
                            records.append(rec)

        ds.close()
        return records

    def _build_record_from_grid_point(
        self,
        lat: float,
        lon: float,
        date_str: str,
        timestamp_iso: str,
        var_type: str,
        var_name: str,
        value: float,
        units: str,
        file_name: str,
        threshold_filter_only: bool = True,
    ) -> Optional[TrainingRecord]:
        """
        Normalizes units, derives conservative meteorological labels, and formats canonical TrainingRecord.
        """
        # Unit Normalization
        # Rainfall: mm/day
        # Temperature: Celsius
        norm_val = value
        if "kelvin" in units or "k" == units.strip():
            norm_val = norm_val - 273.15

        category = WeatherEventCategory.UNKNOWN
        severity = 1
        label_type = "UNLABELED"
        conf = 0.85
        text = ""

        if var_type == "RAINFALL":
            # Rainfall thresholds based on official IMD classifications:
            # Heavy: >= 64.5 mm, Very Heavy: >= 115.6 mm, Extremely Heavy: >= 204.5 mm
            if norm_val >= 204.5:
                category = WeatherEventCategory.RAINFALL
                severity = 4
                label_type = "STRONG"
                text = f"[IMD CRS Gridded Observation] Extremely Heavy Rainfall recorded: {norm_val:.1f} mm/day on {date_str} at grid ({lat:.2f}N, {lon:.2f}E)."
            elif norm_val >= 115.6:
                category = WeatherEventCategory.RAINFALL
                severity = 3
                label_type = "STRONG"
                text = f"[IMD CRS Gridded Observation] Very Heavy Rainfall recorded: {norm_val:.1f} mm/day on {date_str} at grid ({lat:.2f}N, {lon:.2f}E)."
            elif norm_val >= 64.5:
                category = WeatherEventCategory.RAINFALL
                severity = 2
                label_type = "STRONG"
                text = f"[IMD CRS Gridded Observation] Heavy Rainfall recorded: {norm_val:.1f} mm/day on {date_str} at grid ({lat:.2f}N, {lon:.2f}E)."
            elif norm_val >= 15.6:
                category = WeatherEventCategory.RAINFALL
                severity = 2
                label_type = "WEAK"
                text = f"[IMD CRS Gridded Observation] Moderate Rainfall recorded: {norm_val:.1f} mm/day on {date_str} at grid ({lat:.2f}N, {lon:.2f}E)."
            elif not threshold_filter_only and norm_val > 0.0:
                category = WeatherEventCategory.RAINFALL
                severity = 1
                label_type = "WEAK"
                text = f"[IMD CRS Gridded Observation] Light Rainfall recorded: {norm_val:.1f} mm/day on {date_str} at grid ({lat:.2f}N, {lon:.2f}E)."
            else:
                if threshold_filter_only:
                    return None

        elif var_type in ("TMAX", "TEMPERATURE"):
            # Temperature thresholds: Heatwave Plains >= 40.0C, Severe >= 45.0C
            if norm_val >= 45.0:
                category = WeatherEventCategory.HEATWAVE
                severity = 4
                label_type = "STRONG"
                text = f"[IMD CRS Gridded Observation] Extreme Maximum Temperature recorded: {norm_val:.1f}°C on {date_str} at grid ({lat:.2f}N, {lon:.2f}E)."
            elif norm_val >= 42.0:
                category = WeatherEventCategory.HEATWAVE
                severity = 3
                label_type = "STRONG"
                text = f"[IMD CRS Gridded Observation] Severe Heat Temperature recorded: {norm_val:.1f}°C on {date_str} at grid ({lat:.2f}N, {lon:.2f}E)."
            elif norm_val >= 40.0:
                category = WeatherEventCategory.HEATWAVE
                severity = 2
                label_type = "WEAK"
                text = f"[IMD CRS Gridded Observation] High Temperature recorded: {norm_val:.1f}°C on {date_str} at grid ({lat:.2f}N, {lon:.2f}E)."
            else:
                if threshold_filter_only:
                    return None

        if not text:
            return None

        rec_id = f"imd_crs_{lat:.2f}_{lon:.2f}_{date_str}_{var_name.lower()}"

        return TrainingRecord(
            id=rec_id,
            text=text,
            category=category,
            severity=severity,
            timestamp=timestamp_iso,
            latitude=round(lat, 4),
            longitude=round(lon, 4),
            source_type="IMD_HISTORICAL_CRS",
            source_id=f"imd_crs_{file_name}_{date_str}",
            verified=True,
            verification_status="VERIFIED",
            label_source="IMD_PUNE_CRS_GRID",
            label_confidence=conf,
            label_method="OFFICIAL_GOVERNMENT_GRIDDED_OBSERVATION",
            language="en",
            location_method=LocationMethod.EXACT_COORDINATE.value,
            conflict_flag=False,
            candidate_labels=[category.value] if category != WeatherEventCategory.UNKNOWN else [],
            metadata={
                "original_file": file_name,
                "original_variable": var_name,
                "variable_type": var_type,
                "measurement_value": norm_val,
                "unit": "mm/day" if var_type == "RAINFALL" else "°C",
                "date": date_str,
                "label_type": label_type,
                "grid_resolution": "0.25deg" if var_type == "RAINFALL" else "0.50deg",
                "agency": "India Meteorological Department (CRS Pune)",
            },
        )

    @staticmethod
    def _detect_coords(ds) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Detects latitude, longitude, and time coordinate names across NetCDF variants."""
        lat_coord = None
        lon_coord = None
        time_coord = None

        coord_and_dim_names = list(ds.coords.keys()) + list(ds.sizes.keys())
        for name in coord_and_dim_names:
            n_low = str(name).lower()
            if not lat_coord and n_low in LAT_COORD_NAMES:
                lat_coord = str(name)
            elif not lon_coord and n_low in LON_COORD_NAMES:
                lon_coord = str(name)
            elif not time_coord and n_low in TIME_COORD_NAMES:
                time_coord = str(name)

        return lat_coord, lon_coord, time_coord


def main():
    parser = argparse.ArgumentParser(description="SkyPulse IMD Historical CRS Gridded Dataset Tool")
    parser.add_argument("--inspect", type=str, default=None, help="Inspect NetCDF file structure and compatibility")
    parser.add_argument("--file", type=str, default=None, help="Path to IMD CRS NetCDF file for extraction/preview")
    parser.add_argument("--start-date", type=str, default="2024-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default="2024-01-07", help="End date (YYYY-MM-DD)")
    parser.add_argument("--preview", type=int, default=10, help="Number of records to preview")

    args = parser.parse_args()
    adapter = IMDHistoricalCRSAdapter()

    if args.inspect:
        print("\n" + "=" * 65)
        print("IMD CRS FILE INSPECTION REPORT")
        print("=" * 65)
        try:
            res = adapter.inspect_file(args.inspect)
            print(f"File:         {res['file_name']} ({res['file_size_mb']} MB)")
            print(f"Format:       {res['format']}")
            print(f"Dimensions:   {res['dimensions']}")
            print(f"Variables:    {res['variables']}")
            print(f"Lat Range:    {res['lat_range']}")
            print(f"Lon Range:    {res['lon_range']}")
            print(f"Date Range:   {res['date_range']}")
            print(f"Compatible:   {res['compatible']}")
            if res.get("errors"):
                print(f"Errors:       {res['errors']}")
        except Exception as e:
            print(f"Inspection Error: {e}")
        print("=" * 65 + "\n")
        return

    if args.file:
        print("\n" + "=" * 65)
        print(f"IMD CRS DATASET PREVIEW (Date Range: {args.start_date} to {args.end_date})")
        print("=" * 65)
        try:
            records = adapter.parse_netcdf(
                file_path=args.file,
                start_date=args.start_date,
                end_date=args.end_date,
                max_records=args.preview,
            )
            print(f"Extracted {len(records)} sample records:")
            for idx, r in enumerate(records[:args.preview]):
                print(f"\n[{idx + 1}] ID: {r.id}")
                print(f"    Text:     {r.text}")
                print(f"    Category: {r.category.value} | Severity: {r.severity}")
                print(f"    Location: ({r.latitude}, {r.longitude}) | Time: {r.timestamp}")
                print(f"    Source:   {r.source_type} ({r.label_source})")
        except Exception as e:
            print(f"Preview Error: {e}")
        print("=" * 65 + "\n")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
