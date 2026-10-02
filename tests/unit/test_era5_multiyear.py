"""
Unit tests for SkyPulse Multi-Year ERA5 Ingestion, Resumable Caching, Drive Paths & Splitter.
Strictly verifies:
1. 2024 and 2025 records go only to TRAIN
2. Jan-Jun 2026 goes only to VALIDATION
3. Jul 2026 onward goes only to TEST
4. No timestamp overlap (temporal leakage check)
5. No future/unavailable ERA5 dates are generated (safe truncation)
6. Completed monthly chunks are skipped (resumability)
7. v1 is never overwritten by v2 builds
8. ERA5 labels remain weak/provenance-tagged (no fabricated strong labels for FLOODING/THUNDERSTORM/DUST_STORM)
"""

import os
import json
import pytest
import pandas as pd
from datetime import datetime, timezone, date, timedelta

from backend.ml.schemas import (
    TrainingRecord,
    WeatherEventCategory,
    DatasetReadiness,
)
from ml_training.era5_adapter import (
    ERA5Adapter,
    ERA5MultiYearConfig,
    INDIA_BOUNDING_BOX,
    SUPPORTED_VARIABLES,
)
from ml_training.splitter import DatasetSplitter
from ml_training.build_dataset import SkyPulseDatasetBuilder


@pytest.fixture
def era5_adapter(tmp_path):
    cache_dir = str(tmp_path / "era5_cache")
    return ERA5Adapter(cache_dir=cache_dir)


@pytest.fixture
def splitter():
    return DatasetSplitter()


def test_multiyear_monthly_slices_generation(era5_adapter):
    """Test 1: Generates calendar-aligned monthly slices across multi-year horizon."""
    slices = era5_adapter.get_monthly_slices("2024-01-01", "2026-03-15")
    assert len(slices) == 27  # 12 (2024) + 12 (2025) + 3 (2026 Jan, Feb, Mar)
    
    assert slices[0]["year"] == "2024"
    assert slices[0]["month"] == "01"
    assert slices[0]["num_days"] == 31
    assert slices[0]["days"][0] == "01"
    assert slices[0]["days"][-1] == "31"

    # Leap year 2024 Feb
    assert slices[1]["year"] == "2024"
    assert slices[1]["month"] == "02"
    assert slices[1]["num_days"] == 29

    # Non-leap year 2025 Feb
    assert slices[13]["year"] == "2025"
    assert slices[13]["month"] == "02"
    assert slices[13]["num_days"] == 28

    # Partial month 2026 Mar
    assert slices[-1]["year"] == "2026"
    assert slices[-1]["month"] == "03"
    assert slices[-1]["num_days"] == 15
    assert slices[-1]["days"][-1] == "15"


def test_no_future_unavailable_era5_dates_generated(era5_adapter):
    """Test 2: Future/unavailable dates beyond CDS lag are safely truncated, never fabricated."""
    future_date = "2028-12-31"
    actual_date, is_truncated = era5_adapter.discover_latest_available_date(future_date)
    assert is_truncated is True
    
    today_utc = datetime.now(timezone.utc).date()
    expected_max = (today_utc - timedelta(days=5)).strftime("%Y-%m-%d")
    assert actual_date == expected_max
    assert actual_date < future_date

    # Past date within availability window remains unchanged
    past_date = "2024-06-15"
    actual_past, past_truncated = era5_adapter.discover_latest_available_date(past_date)
    assert past_truncated is False
    assert actual_past == "2024-06-15"


def test_completed_monthly_chunks_are_skipped(era5_adapter, tmp_path):
    """Test 3: Completed valid monthly Parquet chunks are skipped; corrupt/missing chunks are detected."""
    cache_dir = str(tmp_path / "monthly_chunks")
    year, month = "2024", "01"
    
    # 1. Non-existent chunk
    assert era5_adapter.is_chunk_valid(year, month, cache_dir) is False

    # 2. Corrupted chunk (parquet exists but no metadata JSON)
    os.makedirs(cache_dir, exist_ok=True)
    parquet_path = os.path.join(cache_dir, f"era5_{year}_{month}.parquet")
    df = pd.DataFrame([{"text": "Sample ERA5", "category": "RAINFALL", "severity": 3}])
    df.to_parquet(parquet_path, engine="pyarrow")
    
    assert era5_adapter.is_chunk_valid(year, month, cache_dir) is False

    # 3. Valid chunk with completed metadata JSON -> SKIP
    meta_path = os.path.join(cache_dir, f"era5_{year}_{month}.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"status": "COMPLETED", "records_count": 100}, f)

    assert era5_adapter.is_chunk_valid(year, month, cache_dir) is True


def test_fixed_chronological_splits_and_no_timestamp_overlap(splitter):
    """Test 4: 2024-2025 -> TRAIN only, 2026 H1 -> VAL only, 2026 H2+ -> TEST only, zero overlap."""
    records = []
    # 2024 records (Train)
    for d in [1, 100, 200]:
        ts = (datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc) + timedelta(days=d)).isoformat()
        records.append(TrainingRecord(text=f"2024 rec {d}", category=WeatherEventCategory.RAINFALL, severity=2, timestamp=ts))
    
    # 2025 records (Train)
    for d in [1, 100, 200, 360]:
        ts = (datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc) + timedelta(days=d)).isoformat()
        records.append(TrainingRecord(text=f"2025 rec {d}", category=WeatherEventCategory.HEATWAVE, severity=3, timestamp=ts))

    # 2026 H1 records (Validation: 2026-01-01 to 2026-06-30)
    for d in [10, 50, 100, 175]:
        ts = (datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc) + timedelta(days=d)).isoformat()
        records.append(TrainingRecord(text=f"2026 H1 rec {d}", category=WeatherEventCategory.FOG, severity=2, timestamp=ts))

    # 2026 H2 records (Test: 2026-07-01 onwards)
    for d in [190, 220, 250]:
        ts = (datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc) + timedelta(days=d)).isoformat()
        records.append(TrainingRecord(text=f"2026 H2 rec {d}", category=WeatherEventCategory.STRONG_WINDS, severity=4, timestamp=ts))

    train, val, test, split_meta = splitter.split_chronological(
        records,
        train_end_date="2025-12-31",
        val_end_date="2026-06-30",
        test_start_date="2026-07-01",
    )

    # 1. Exact count verification
    assert len(train) == 7  # 3 (2024) + 4 (2025)
    assert len(val) == 4    # 4 (2026 H1)
    assert len(test) == 3   # 3 (2026 H2)

    # 2. Strict Partition Year Verification
    for r in train:
        assert r.timestamp[:4] in ["2024", "2025"]
    for r in val:
        assert r.timestamp[:7] in ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
    for r in test:
        assert r.timestamp[:7] in ["2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12"]

    # 3. No Timestamp Overlap
    assert split_meta["temporal_leakage_detected"] is False
    assert split_meta["spatial_event_leakage_detected"] is False
    assert split_meta["train_end"] < split_meta["val_start"]
    assert split_meta["val_end"] < split_meta["test_start"]


def test_era5_weak_label_provenance_and_semantics():
    """Test 5: ERA5 records are strictly weak/provenance-tagged and NEVER manufactured as strong ground truth."""
    adapter = ERA5Adapter()
    
    # Heavy rainfall -> WEAK threshold label
    raw_point_rain = {
        "2m_temperature": 300.15,
        "2m_dewpoint_temperature": 298.15,
        "total_precipitation": 0.085,  # 85 mm
        "10m_u_component_of_wind": 5.0,
        "10m_v_component_of_wind": 5.0,
        "surface_pressure": 100500.0,
    }

    rec = adapter.generate_weak_label_record(raw_point_rain, lat=22.5, lon=78.5, timestamp="2024-05-15T00:00:00Z")
    assert rec is not None
    assert rec.category == WeatherEventCategory.RAINFALL
    assert rec.source_type == "ERA5_REANALYSIS"
    assert rec.label_source == "ERA5_METEOROLOGICAL_REANALYSIS"
    assert rec.label_method == "WEAK_METEOROLOGICAL_THRESHOLD"
    assert rec.verified is False
    assert rec.verification_status == "UNVERIFIED"
    assert rec.location_method == "ERA5_GRID"
    assert rec.reanalysis_features["era5_precipitation_mm"] == 85.0

    # ERA5 does NOT derive strong ground truth for FLOODING, THUNDERSTORM, DUST_STORM
    assert rec.category not in [WeatherEventCategory.FLOODING, WeatherEventCategory.THUNDERSTORM, WeatherEventCategory.DUST_STORM]


def test_v1_is_never_overwritten_by_v2_build(tmp_path, monkeypatch):
    """Test 6: Building v2 writes to datasets/v2 without modifying or deleting existing v1 artifacts."""
    datasets_root = tmp_path / "datasets"
    v1_dir = datasets_root / "v1"
    v1_dir.mkdir(parents=True)
    
    # Create existing v1 artifact
    v1_manifest_path = v1_dir / "dataset_manifest.json"
    with open(v1_manifest_path, "w", encoding="utf-8") as f:
        json.dump({"dataset_version": "v1", "records_count": 500}, f)

    builder_v2 = SkyPulseDatasetBuilder(output_dir=str(datasets_root), output_version="v2")
    monkeypatch.setattr(builder_v2.era5_adapter, "process_era5_training_records", lambda cfg: [])

    result = builder_v2.build(
        sources=["era5", "imd"],
        start_date="2024-01-01",
        end_date="2026-12-31",
        train_end_date="2025-12-31",
        val_end_date="2026-06-30",
        test_start_date="2026-07-01",
        latest_available=True,
    )

    assert result["version"] == "v2"
    assert os.path.exists(os.path.join(str(datasets_root), "v2", "dataset_manifest.json"))
    
    # Verify v1 is intact and untouched
    with open(v1_manifest_path, "r", encoding="utf-8") as f:
        v1_data = json.load(f)
    assert v1_data["dataset_version"] == "v1"
    assert v1_data["records_count"] == 500


def test_drive_root_validation_fails_on_missing_mount(tmp_path):
    """Test 7: Builder raises clear FileNotFoundError if Google Drive path is not mounted."""
    non_existent_drive = str(tmp_path / "non_existent_drive_mount_123")
    with pytest.raises(FileNotFoundError) as exc_info:
        SkyPulseDatasetBuilder(drive_root=non_existent_drive)
    assert "DRIVE_ROOT_NOT_FOUND" in str(exc_info.value)


def test_drive_root_success_when_mounted_and_manifest_fields(tmp_path, monkeypatch):
    """Test 8: Builder mounts Drive root, prepares datasets/v2/monthly_chunks, and exports complete manifest."""
    valid_drive = tmp_path / "MyDrive" / "SkyPulse_ML"
    valid_drive.mkdir(parents=True)
    
    builder = SkyPulseDatasetBuilder(drive_root=str(valid_drive), output_version="v2")
    assert builder.output_dir == os.path.join(str(valid_drive), "datasets")
    assert builder.era5_cache_dir == os.path.join(str(valid_drive), "datasets", "v2", "monthly_chunks")

    monkeypatch.setattr(builder.era5_adapter, "process_era5_training_records", lambda cfg: [])

    result = builder.build(
        sources=["era5", "imd"],
        start_date="2024-01-01",
        end_date="2026-12-31",
        train_end_date="2025-12-31",
        val_end_date="2026-06-30",
        test_start_date="2026-07-01",
        latest_available=True,
    )

    manifest = result["manifest"]
    assert manifest["dataset_version"] == "v2"
    assert manifest["requested_start_date"] == "2024-01-01"
    assert manifest["requested_end_date"] == "2026-12-31"
    assert "actual_available_end_date" in manifest
    assert manifest["train_start"] == "2024-01-01"
    assert manifest["train_end"] == "2025-12-31"
    assert manifest["validation_start"] == "2026-01-01"
    assert manifest["validation_end"] == "2026-06-30"
    assert manifest["test_start"] == "2026-07-01"
    assert "test_end" in manifest
    assert manifest["split_policy"] == "fixed_chronological_date_boundaries"


def test_inspect_era5_file_signatures(tmp_path):
    """Test 9: inspect_era5_file correctly detects file signatures, empty files, and error payloads."""
    # 1. Non-existent
    res_none = ERA5Adapter.inspect_era5_file(str(tmp_path / "non_existent.nc"))
    assert res_none["exists"] is False
    assert res_none["is_valid"] is False

    # 2. Empty file (0 bytes)
    empty_file = tmp_path / "empty.nc"
    empty_file.write_bytes(b"")
    res_empty = ERA5Adapter.inspect_era5_file(str(empty_file))
    assert res_empty["exists"] is True
    assert res_empty["size_bytes"] == 0
    assert res_empty["detected_format"] == "EMPTY"
    assert res_empty["is_valid"] is False

    # 3. HTML Error response
    html_file = tmp_path / "error.html"
    html_file.write_bytes(b"<!DOCTYPE html><html><body>502 Bad Gateway</body></html>")
    res_html = ERA5Adapter.inspect_era5_file(str(html_file))
    assert res_html["detected_format"] == "HTML_ERROR"
    assert res_html["is_valid"] is False

    # 4. JSON Error response
    json_file = tmp_path / "error.json"
    json_file.write_bytes(b'{"error": "Request rejected", "code": 403}')
    res_json = ERA5Adapter.inspect_era5_file(str(json_file))
    assert res_json["detected_format"] == "JSON_ERROR"
    assert res_json["is_valid"] is False

    # 5. HDF5 / NetCDF4 Signature
    hdf_file = tmp_path / "sample_hdf5.nc"
    hdf_file.write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x00" * 100)
    res_hdf = ERA5Adapter.inspect_era5_file(str(hdf_file))
    assert res_hdf["detected_format"] == "HDF5_NETCDF4"
    assert res_hdf["is_valid"] is True

    # 6. Classic NetCDF Signature
    cdf_file = tmp_path / "sample_classic.nc"
    cdf_file.write_bytes(b"CDF\x02" + b"\x00" * 100)
    res_cdf = ERA5Adapter.inspect_era5_file(str(cdf_file))
    assert res_cdf["detected_format"] == "NETCDF_CLASSIC"
    assert res_cdf["is_valid"] is True

    # 7. ZIP archive Signature
    zip_file = tmp_path / "sample.zip"
    zip_file.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
    res_zip = ERA5Adapter.inspect_era5_file(str(zip_file))
    assert res_zip["detected_format"] == "ZIP_ARCHIVE"
    assert res_zip["is_valid"] is True


def test_open_era5_dataset_validation_failures(tmp_path):
    """Test 10: open_era5_dataset raises clear descriptive error when opening non-NetCDF or corrupt files."""
    # 1. Non-existent file
    with pytest.raises(FileNotFoundError):
        ERA5Adapter.open_era5_dataset(str(tmp_path / "missing.nc"))

    # 2. HTML error file
    html_file = tmp_path / "gateway_error.nc"
    html_file.write_bytes(b"<html><head><title>504 Gateway Timeout</title></head></html>")
    with pytest.raises(ValueError) as exc_info:
        ERA5Adapter.open_era5_dataset(str(html_file))
    assert "Downloaded CDS file is not a readable NetCDF file" in str(exc_info.value)
    assert "HTML_ERROR" in str(exc_info.value)


def test_corrupt_chunk_invalidation_and_reprocessing(tmp_path, era5_adapter):
    """Test 11: Incomplete or corrupt monthly chunk is not treated as completed."""
    cache_dir = str(tmp_path / "monthly_chunks")
    os.makedirs(cache_dir, exist_ok=True)
    year, month = "2024", "01"
    
    p_path = os.path.join(cache_dir, f"era5_{year}_{month}.parquet")
    m_path = os.path.join(cache_dir, f"era5_{year}_{month}.json")

    # Incomplete chunk (status == FAILED)
    with open(m_path, "w", encoding="utf-8") as f:
        json.dump({"status": "FAILED: NetCDF error", "records_count": 0}, f)
    with open(p_path, "wb") as f:
        f.write(b"corrupt")

    assert era5_adapter.is_chunk_valid(year, month, cache_dir) is False

