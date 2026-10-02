"""
Script to download and validate raw monthly ERA5 daily statistics ZIP files
from Copernicus CDS for SkyPulse weather-data ingestion pipeline.

Dataset: derived-era5-single-levels-daily-statistics
Period: 2024-02 through 2026-09 (2026-09 has days 01-26 only)
Total: 32 monthly ZIP files saved to raw_era5/
"""

import os
import sys
import time
import json
import hashlib
import zipfile
import calendar
from pathlib import Path
import cdsapi

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "raw_era5"
MANIFEST_PATH = OUTPUT_DIR / "download_manifest.json"

DATASET_NAME = "derived-era5-single-levels-daily-statistics"

VARIABLES = [
    "2m_temperature",
    "2m_dewpoint_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "mean_sea_level_pressure",
    "total_precipitation",
    "surface_pressure",
]

AREA = [37.5, 68.0, 6.5, 97.5] # North, West, South, East

def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def validate_zip(file_path: Path) -> tuple[bool, str, list[str]]:
    """Validates ZIP signature, integrity, and checks for .nc files."""
    if not file_path.exists():
        return False, "File does not exist", []
    
    if file_path.stat().st_size < 100:
        return False, "File too small (likely error response)", []
    
    # Check magic header
    with open(file_path, "rb") as f:
        magic = f.read(4)
        if magic != b"PK\x03\x04":
            return False, f"Invalid magic header: {magic!r}", []
            
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            corrupt = zf.testzip()
            if corrupt is not None:
                return False, f"Corrupted file inside ZIP: {corrupt}", []
            
            names = zf.namelist()
            nc_files = [n for n in names if n.endswith(".nc")]
            if not nc_files:
                return False, f"No NetCDF (.nc) files found in ZIP. Files: {names}", names
            
            return True, "Valid ZIP with NetCDF contents", names
    except Exception as e:
        return False, f"ZIP extraction/inspection error: {e}", []

def get_month_days(year: int, month: int) -> list[str]:
    if year == 2026 and month == 9:
        num_days = 26
    else:
        num_days = calendar.monthrange(year, month)[1]
    return [f"{d:02d}" for d in range(1, num_days + 1)]

def get_target_months() -> list[tuple[int, int]]:
    months = []
    # 2024: 02..12
    for m in range(2, 13):
        months.append((2024, m))
    # 2025: 01..12
    for m in range(1, 13):
        months.append((2025, m))
    # 2026: 01..09
    for m in range(1, 10):
        months.append((2026, m))
    return months

def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_manifest(manifest: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temp_manifest = MANIFEST_PATH.with_suffix(".tmp")
    with open(temp_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    temp_manifest.replace(MANIFEST_PATH)

def download_month(client: cdsapi.Client, year: int, month: int, max_retries: int = 3) -> dict:
    month_key = f"{year:04d}-{month:02d}"
    filename = f"era5_{year:04d}_{month:02d}.zip"
    target_path = OUTPUT_DIR / filename
    days = get_month_days(year, month)
    
    # Check if already valid
    is_valid, msg, members = validate_zip(target_path)
    if is_valid:
        size_mb = round(target_path.stat().st_size / (1024 * 1024), 2)
        sha = compute_sha256(target_path)
        print(f"[{month_key}] Already exists and valid ({size_mb} MB). Skipping download.")
        return {
            "status": "COMPLETED",
            "file": f"raw_era5/{filename}",
            "size_mb": size_mb,
            "sha256": sha,
            "days": len(days),
            "validation": "PASS",
            "members": members,
            "message": "Existing file validated"
        }
    
    request_params = {
        "product_type": "reanalysis",
        "variable": VARIABLES,
        "year": str(year),
        "month": f"{month:02d}",
        "day": days,
        "daily_statistic": "daily_mean",
        "time_zone": "utc+05:30",
        "frequency": "1_hourly",
        "area": AREA,
        "format": "netcdf",
    }
    
    for attempt in range(1, max_retries + 1):
        print(f"\n>>> [{month_key}] Downloading (Attempt {attempt}/{max_retries}) with {len(days)} days...")
        temp_download = OUTPUT_DIR / f"{filename}.part"
        if temp_download.exists():
            temp_download.unlink()
            
        try:
            client.retrieve(DATASET_NAME, request_params, str(temp_download))
            
            # Validate downloaded temp file
            is_val, val_msg, members = validate_zip(temp_download)
            if not is_val:
                print(f"[{month_key}] Download validation failed: {val_msg}")
                if temp_download.exists():
                    temp_download.unlink()
                raise ValueError(f"Downloaded file validation failed: {val_msg}")
            
            # Rename temp to target
            if target_path.exists():
                target_path.unlink()
            temp_download.replace(target_path)
            
            size_mb = round(target_path.stat().st_size / (1024 * 1024), 2)
            sha = compute_sha256(target_path)
            print(f"[{month_key}] SUCCESS: Saved to {target_path.name} ({size_mb} MB, SHA256: {sha[:12]}...)")
            
            return {
                "status": "COMPLETED",
                "file": f"raw_era5/{filename}",
                "size_mb": size_mb,
                "sha256": sha,
                "days": len(days),
                "validation": "PASS",
                "members": members,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        except Exception as e:
            print(f"[{month_key}] Error during attempt {attempt}: {e}")
            if temp_download.exists():
                temp_download.unlink()
            if attempt < max_retries:
                backoff = attempt * 15
                print(f"[{month_key}] Backing off for {backoff}s before retry...")
                time.sleep(backoff)
            else:
                return {
                    "status": "FAILED",
                    "file": f"raw_era5/{filename}",
                    "days": len(days),
                    "validation": "FAIL",
                    "error": str(e)
                }

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    
    print("=" * 60)
    print("SkyPulse ERA5 Monthly Daily Statistics Downloader")
    print(f"Dataset: {DATASET_NAME}")
    print(f"Variables: {', '.join(VARIABLES)}")
    print(f"Bounding Box: {AREA}")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)
    
    client = cdsapi.Client()
    target_months = get_target_months()
    print(f"Total target months: {len(target_months)} (2024-02 through 2026-09)\n")
    
    results = {}
    completed_count = 0
    failed_count = 0
    skipped_count = 0
    
    for year, month in target_months:
        month_key = f"{year:04d}-{month:02d}"
        
        # Check manifest first if already marked completed & file is valid
        if month_key in manifest and manifest[month_key].get("status") == "COMPLETED":
            target_path = OUTPUT_DIR / f"era5_{year:04d}_{month:02d}.zip"
            is_valid, msg, members = validate_zip(target_path)
            if is_valid:
                print(f"[{month_key}] Manifest & File OK. Skipping.")
                results[month_key] = manifest[month_key]
                skipped_count += 1
                continue
                
        res = download_month(client, year, month)
        manifest[month_key] = res
        save_manifest(manifest)
        results[month_key] = res
        
        if res.get("status") == "COMPLETED":
            completed_count += 1
        else:
            failed_count += 1
            
    print("\n" + "=" * 80)
    print("DOWNLOAD SUMMARY TABLE")
    print("=" * 80)
    print(f"{'Month':<10} | {'Status':<10} | {'File':<20} | {'Size MB':<8} | {'SHA256 (first 12)':<18} | {'Days':<5} | {'Validation':<10}")
    print("-" * 80)
    
    total_size_mb = 0.0
    for year, month in target_months:
        month_key = f"{year:04d}-{month:02d}"
        info = results.get(month_key, {})
        status = info.get("status", "UNKNOWN")
        fname = Path(info.get("file", f"raw_era5/era5_{year}_{month:02d}.zip")).name
        size = info.get("size_mb", 0.0)
        total_size_mb += size if isinstance(size, (int, float)) else 0.0
        sha = info.get("sha256", "N/A")[:12] if info.get("sha256") else "N/A"
        days = info.get("days", 0)
        val = info.get("validation", "FAIL")
        print(f"{month_key:<10} | {status:<10} | {fname:<20} | {str(size):<8} | {sha:<18} | {str(days):<5} | {val:<10}")
        
    print("-" * 80)
    print(f"Total target files: {len(target_months)}")
    print(f"Successfully downloaded in this run: {completed_count}")
    print(f"Skipped (already valid): {skipped_count}")
    print(f"Failed: {failed_count}")
    print(f"Total disk usage: {total_size_mb:.2f} MB")
    print(f"Manifest location: {MANIFEST_PATH}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 80)

if __name__ == "__main__":
    main()
