"""
Unit tests for Step 6 IMD Historical CRS Gridded Dataset Adapter.
=================================================================
Tests NetCDF parsing, coordinate extraction, unit conversion, India bounding box
spatial filtering, date range filtering, provenance preservation, and error handling.

NOTE: Test fixtures generated in this module are temporary synthetic fixtures used
STRICTLY for testing parser functionality and are NOT used as training data.
"""

import os
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from ml.schemas import WeatherEventCategory
from ml_training.imd_historical_adapter import (
    IMDHistoricalCRSAdapter,
    IMD_INDIA_BOUNDS,
)


@pytest.fixture
def adapter(tmp_path):
    return IMDHistoricalCRSAdapter(data_dir=str(tmp_path))


@pytest.fixture
def sample_rainfall_nc(tmp_path):
    """
    Creates a small NetCDF test fixture mimicking IMD Pune 0.25 deg daily rainfall files.
    """
    import xarray as xr

    # Latitudes: 18.0 to 22.0 (inside India), Longitudes: 72.0 to 76.0 (inside India)
    lats = np.array([18.0, 19.0, 20.0, 21.0, 22.0], dtype=np.float32)
    lons = np.array([72.0, 73.0, 74.0, 75.0, 76.0], dtype=np.float32)
    dates = pd.date_range("2024-07-01", periods=3, freq="D")

    # Shape: (3, 5, 5)
    data = np.zeros((3, 5, 5), dtype=np.float32)
    # Day 1: normal light rain
    data[0, 2, 2] = 20.5
    # Day 2: Heavy rainfall (85.0 mm)
    data[1, 2, 2] = 85.0
    # Day 2: Very Heavy rainfall (140.0 mm)
    data[1, 3, 3] = 140.0
    # Day 3: Extremely Heavy rainfall (220.0 mm)
    data[2, 1, 1] = 220.0

    ds = xr.Dataset(
        data_vars={
            "rf": (["time", "lat", "lon"], data, {"units": "mm/day", "long_name": "IMD Daily Rainfall"})
        },
        coords={
            "time": dates,
            "lat": lats,
            "lon": lons,
        },
        attrs={"title": "IMD Pune High Resolution Gridded Rainfall Test Fixture"}
    )

    file_path = str(tmp_path / "Rainfall_0.25_2024_test.nc")
    ds.to_netcdf(file_path)
    ds.close()
    return file_path


@pytest.fixture
def sample_temperature_nc(tmp_path):
    """
    Creates a small NetCDF test fixture mimicking IMD Pune daily temperature files.
    """
    import xarray as xr

    lats = np.array([25.0, 26.0, 27.0], dtype=np.float32)
    lons = np.array([75.0, 76.0, 77.0], dtype=np.float32)
    dates = pd.date_range("2024-05-15", periods=2, freq="D")

    # Shape: (2, 3, 3)
    data = np.full((2, 3, 3), 35.0, dtype=np.float32)
    # Heatwave temperature (42.5 C)
    data[0, 1, 1] = 42.5
    # Extreme Heatwave temperature (46.2 C)
    data[1, 1, 1] = 46.2

    ds = xr.Dataset(
        data_vars={
            "tmax": (["time", "lat", "lon"], data, {"units": "Celsius", "long_name": "Maximum Temperature"})
        },
        coords={
            "time": dates,
            "lat": lats,
            "lon": lons,
        },
        attrs={"title": "IMD Pune Daily Maximum Temperature Test Fixture"}
    )

    file_path = str(tmp_path / "Tmax_0.5_2024_test.nc")
    ds.to_netcdf(file_path)
    ds.close()
    return file_path


def test_inspect_file_missing(adapter):
    with pytest.raises(FileNotFoundError):
        adapter.inspect_file("non_existent_file.nc")


def test_inspect_file_netcdf_fixture(adapter, sample_rainfall_nc):
    info = adapter.inspect_file(sample_rainfall_nc)
    assert info["compatible"] is True
    assert "rf" in info["variables"]
    assert info["primary_variable"] == "rf"
    assert info["lat_range"] == [18.0, 22.0]
    assert info["lon_range"] == [72.0, 76.0]
    assert info["date_range"]["start"] == "2024-07-01"
    assert info["date_range"]["end"] == "2024-07-03"
    assert info["estimated_record_count"] == 3 * 5 * 5


def test_parse_netcdf_rainfall_conversion_and_provenance(adapter, sample_rainfall_nc):
    records = adapter.parse_netcdf(sample_rainfall_nc, start_date="2024-07-01", end_date="2024-07-03")
    assert len(records) > 0

    # Verify categories & severities
    categories = {r.category for r in records}
    assert WeatherEventCategory.RAINFALL in categories

    # Find the heavy, very heavy, and extreme heavy records
    heavy_recs = [r for r in records if "85.0 mm" in r.text or "140.0 mm" in r.text or "220.0 mm" in r.text]
    assert len(heavy_recs) == 3

    extreme_rec = [r for r in records if "220.0 mm" in r.text][0]
    assert extreme_rec.severity == 4
    assert extreme_rec.source_type == "IMD_HISTORICAL_CRS"
    assert extreme_rec.verified is True
    assert extreme_rec.label_source == "IMD_PUNE_CRS_GRID"
    assert extreme_rec.label_confidence == 0.85
    assert extreme_rec.metadata["agency"] == "India Meteorological Department (CRS Pune)"
    assert extreme_rec.metadata["original_variable"] == "rf"
    assert extreme_rec.metadata["unit"] == "mm/day"
    assert extreme_rec.metadata["label_type"] == "STRONG"


def test_parse_netcdf_temperature_conversion(adapter, sample_temperature_nc):
    records = adapter.parse_netcdf(sample_temperature_nc, start_date="2024-05-15", end_date="2024-05-16")
    assert len(records) >= 2

    # Check heatwave category
    heat_recs = [r for r in records if r.category == WeatherEventCategory.HEATWAVE]
    assert len(heat_recs) >= 2

    extreme_heat = [r for r in heat_recs if r.severity == 4][0]
    assert "46.2°C" in extreme_heat.text
    assert extreme_heat.source_type == "IMD_HISTORICAL_CRS"
    assert extreme_heat.metadata["unit"] == "°C"


def test_india_bounding_box_cropping(adapter, tmp_path):
    import xarray as xr

    # Latitudes spanning outside and inside India: 0.0 to 10.0
    lats = np.array([0.0, 5.0, 10.0, 15.0], dtype=np.float32)  # 0.0 and 5.0 are outside India bounds (min 6.5)
    lons = np.array([75.0, 76.0], dtype=np.float32)
    dates = pd.date_range("2024-08-01", periods=1, freq="D")

    data = np.full((1, 4, 2), 80.0, dtype=np.float32)

    ds = xr.Dataset(
        data_vars={"rf": (["time", "lat", "lon"], data)},
        coords={"time": dates, "lat": lats, "lon": lons},
    )
    fp = str(tmp_path / "crop_test.nc")
    ds.to_netcdf(fp)
    ds.close()

    records = adapter.parse_netcdf(fp)
    # Coordinates in records should all be >= 6.5 and <= 38.5
    for r in records:
        assert r.latitude >= IMD_INDIA_BOUNDS["lat_min"]
        assert r.latitude <= IMD_INDIA_BOUNDS["lat_max"]


def test_date_range_filtering(adapter, sample_rainfall_nc):
    # Only Day 2 (2024-07-02)
    recs_d2 = adapter.parse_netcdf(sample_rainfall_nc, start_date="2024-07-02", end_date="2024-07-02")
    for r in recs_d2:
        assert r.timestamp.startswith("2024-07-02")


def test_missing_variables_error(adapter, tmp_path):
    import xarray as xr

    # NetCDF missing meteorological variables
    ds = xr.Dataset(
        data_vars={"dummy_var": (["time", "lat", "lon"], np.zeros((1, 2, 2)))},
        coords={
            "time": pd.date_range("2024-01-01", periods=1),
            "lat": [20.0, 21.0],
            "lon": [75.0, 76.0],
        }
    )
    fp = str(tmp_path / "invalid_var.nc")
    ds.to_netcdf(fp)
    ds.close()

    with pytest.raises(ValueError, match="No recognizable meteorological variable"):
        adapter.parse_netcdf(fp)


def test_extract_not_configured_when_no_files(tmp_path):
    adapter_empty = IMDHistoricalCRSAdapter(data_dir=str(tmp_path / "empty_dir"))
    res = adapter_empty.extract()
    assert res["status"] == "NOT_CONFIGURED"
    assert len(res["records"]) == 0
