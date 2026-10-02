"""
Unit tests for Step 6: Dataset Quality Engine, Normalization, Labeling, and Alignment.
"""

import pytest
from datetime import datetime, timezone

from backend.ml.schemas import (
    TrainingRecord,
    WeatherEventCategory,
    LabelType,
    LocationMethod,
    DataQualityStatus,
)
from ml_training.quality import DatasetQualityEngine
from ml_training.labeling import LabelingEngine
from ml_training.alignment import AlignmentEngine
from ml_training.era5_adapter import ERA5Adapter, ERA5Config


@pytest.fixture
def quality_engine():
    return DatasetQualityEngine()


@pytest.fixture
def labeling_engine():
    return LabelingEngine()


@pytest.fixture
def alignment_engine():
    return AlignmentEngine()


def test_quality_engine_valid_record(quality_engine):
    raw = {
        "text": "Moderate to heavy rainfall of 75mm recorded across Mumbai district",
        "category": "RAINFALL",
        "severity": 3,
        "timestamp": "2024-07-15T10:00:00Z",
        "latitude": 19.076,
        "longitude": 72.877,
        "source_type": "IMD",
        "source_id": "imd_obs_001",
        "verified": True,
        "metadata": {"rainfall_mm": 75.0, "temp_c": 28.5},
    }
    status, clean_rec, reason = quality_engine.validate_and_clean_record(raw)
    assert status == DataQualityStatus.VALID
    assert clean_rec is not None
    assert clean_rec.latitude == 19.076
    assert clean_rec.longitude == 72.877
    assert clean_rec.metadata["rainfall_mm"] == 75.0


def test_quality_engine_unit_normalization(quality_engine):
    # Test Fahrenheit to Celsius, cm to mm, m/s to km/h, inHg to hPa
    raw = {
        "text": "Weather observation report with mixed international units",
        "timestamp": "2024-05-10T12:00:00Z",
        "latitude": 28.61,
        "longitude": 77.20,
        "source_type": "data.gov.in",
        "metadata": {
            "temp_f": 104.0,       # 104°F = 40.0°C
            "rainfall_cm": 5.0,    # 5 cm = 50.0 mm
            "wind_mps": 10.0,      # 10 m/s = 36.0 km/h
            "pressure_inhg": 29.92,# 29.92 inHg = 1013.2 hPa
            "visibility_m": 500.0, # 500 m = 0.5 km
        }
    }
    status, clean_rec, _ = quality_engine.validate_and_clean_record(raw)
    assert status == DataQualityStatus.VALID
    assert clean_rec is not None
    assert pytest.approx(clean_rec.metadata["temperature_c"], 0.1) == 40.0
    assert pytest.approx(clean_rec.metadata["rainfall_mm"], 0.1) == 50.0
    assert pytest.approx(clean_rec.metadata["wind_speed_kmh"], 0.1) == 36.0
    assert pytest.approx(clean_rec.metadata["pressure_hpa"], 0.1) == 1013.2
    assert pytest.approx(clean_rec.metadata["visibility_km"], 0.1) == 0.5


def test_quality_engine_rejection_impossible_values(quality_engine):
    # Invalid coordinates
    raw_bad_coords = {
        "text": "Station observation with impossible latitude",
        "timestamp": "2024-01-01T00:00:00Z",
        "latitude": 95.0,
        "longitude": 77.0,
    }
    status, rec, reason = quality_engine.validate_and_clean_record(raw_bad_coords)
    assert status == DataQualityStatus.INVALID
    assert "Latitude out of valid range" in reason

    # Impossible physical temperature (e.g. 75°C in India)
    raw_extreme_temp = {
        "text": "Sensory glitch reporting 85C temperature in Delhi",
        "timestamp": "2024-06-01T12:00:00Z",
        "latitude": 28.6,
        "longitude": 77.2,
        "metadata": {"temp_c": 85.0}
    }
    status, rec, reason = quality_engine.validate_and_clean_record(raw_extreme_temp)
    assert status == DataQualityStatus.INVALID
    assert "Impossible temperature" in reason

    # Impossible rainfall (> 1500 mm in 24h)
    raw_extreme_rain = {
        "text": "Corrupted sensor reporting 2500mm rain",
        "timestamp": "2024-06-01T12:00:00Z",
        "latitude": 28.6,
        "longitude": 77.2,
        "metadata": {"rainfall_mm": 2500.0}
    }
    status, rec, reason = quality_engine.validate_and_clean_record(raw_extreme_rain)
    assert status == DataQualityStatus.INVALID
    assert "Impossible rainfall" in reason

    # Future timestamp
    raw_future = {
        "text": "Observation from the distant future",
        "timestamp": "2099-01-01T00:00:00Z",
        "latitude": 28.6,
        "longitude": 77.2,
    }
    status, rec, reason = quality_engine.validate_and_clean_record(raw_future)
    assert status == DataQualityStatus.INVALID
    assert "Future timestamp" in reason


def test_labeling_engine_strong_labels(labeling_engine):
    # IMD Warning record
    rec_imd = TrainingRecord(
        text="IMD RED ALERT: Extremely severe cyclonic storm with heavy rainfall over coastal Andhra",
        category=WeatherEventCategory.UNKNOWN,
        severity=4,
        source_type="IMD",
        source_id="imd_warn_99",
        label_source="IMD_WARNING",
        verified=True,
        verification_status="VERIFIED",
    )
    labeled = labeling_engine.process_record(rec_imd)
    assert labeled.metadata.get("label_type") == "STRONG"
    assert labeled.category in [WeatherEventCategory.CYCLONE, WeatherEventCategory.RAINFALL]
    assert labeled.label_confidence >= 0.90


def test_labeling_engine_weak_labels_from_meteorology(labeling_engine):
    # Observation with 95mm rainfall without explicit category
    rec_obs = TrainingRecord(
        text="AWS Station 42182 24hr accumulated precipitation recorded 95.2mm",
        category=WeatherEventCategory.UNKNOWN,
        severity=2,
        source_type="AWS_STATION",
        source_id="aws_42182",
        metadata={"rainfall_mm": 95.2},
    )
    labeled = labeling_engine.process_record(rec_obs)
    assert labeled.metadata.get("label_type") == "WEAK"
    assert labeled.category == WeatherEventCategory.RAINFALL
    assert labeled.label_confidence == 0.80
    assert labeled.label_method == "METEOROLOGICAL_THRESHOLD_HEAVY_RAIN"


def test_labeling_engine_conflict_resolution(labeling_engine):
    # Conflicting candidate labels (e.g. RAINFALL and FLOODING from citizen vs IMD)
    rec_conflict = TrainingRecord(
        text="Water entering ground floor shops after sudden cloudburst",
        category=WeatherEventCategory.UNKNOWN,
        severity=3,
        source_type="CITIZEN_REPORT",
        source_id="cit_102",
        candidate_labels=["RAINFALL", "FLOODING"],
        metadata={"flood_water_level_ft": 3.0, "rainfall_mm": 80.0},
    )
    labeled = labeling_engine.process_record(rec_conflict)
    # The rule prioritizes FLOODING when waterlogging/flood evidence exists, preserving candidate labels
    assert labeled.conflict_flag is True
    assert labeled.candidate_labels == ["RAINFALL", "FLOODING"]
    assert labeled.category in [WeatherEventCategory.FLOODING, WeatherEventCategory.RAINFALL]


def test_alignment_engine_era5_features(alignment_engine):
    # Test joining ERA5 reanalysis features and calculating derived wind_speed
    records = [
        TrainingRecord(
            text="IMD AWS station report Bhubaneswar",
            category=WeatherEventCategory.RAINFALL,
            severity=2,
            timestamp="2024-06-10T14:00:00Z",
            latitude=20.29,
            longitude=85.82,
            source_type="IMD",
            source_id="imd_bbsr",
        )
    ]

    era5_data = [
        {
            "latitude": 20.25,
            "longitude": 85.75,
            "timestamp": "2024-06-10T14:00:00Z",
            "temperature_2m": 303.15,
            "total_precipitation": 0.025,
            "u_wind_10m": 4.0,
            "v_wind_10m": 3.0,
            "surface_pressure": 1002.0,
            "dewpoint_2m": 298.0,
        }
    ]

    joined = alignment_engine.join_era5_features(records, era5_grid_data=era5_data)
    assert len(joined) == 1
    features = joined[0].reanalysis_features
    assert features is not None
    assert features["era5_temperature_2m"] == 303.15
    assert features["era5_precipitation"] == 0.025
    # wind speed = sqrt(4^2 + 3^2) = 5.0
    assert pytest.approx(features["era5_wind_speed_10m"], 0.01) == 5.0
    assert joined[0].location_method == LocationMethod.NEAREST_ERA5_GRID
