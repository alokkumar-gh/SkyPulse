"""
Unit tests for Step 6: Dataset Splitter, Leakage Prevention, Readiness Evaluation, and Builder.
"""

import os
import json
import pytest
from datetime import datetime, timezone, timedelta

from backend.ml.schemas import (
    TrainingRecord,
    WeatherEventCategory,
    DatasetReadiness,
)
from ml_training.splitter import DatasetSplitter
from ml_training.readiness import ReadinessEngine
from ml_training.build_dataset import SkyPulseDatasetBuilder


@pytest.fixture
def splitter():
    return DatasetSplitter()


@pytest.fixture
def readiness_engine():
    return ReadinessEngine()


def test_splitter_chronological_ordering(splitter):
    base_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    records = []
    for i in range(100):
        records.append(
            TrainingRecord(
                text=f"Weather report sequence event {i}",
                category=WeatherEventCategory.RAINFALL,
                severity=2,
                timestamp=(base_time + timedelta(hours=i)).isoformat(),
                latitude=20.0 + (i * 0.01),
                longitude=78.0 + (i * 0.01),
                source_type="IMD",
                source_id=f"rec_{i}",
                metadata={"canonical_event_id": f"evt_{i // 5}"},
            )
        )

    train, val, test, split_meta = splitter.split_chronological(
        records, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15
    )

    assert len(train) > 0
    assert len(val) > 0
    assert len(test) > 0
    assert len(train) + len(val) + len(test) == 100

    # Ensure temporal ordering: train_end <= val_start <= test_start
    assert split_meta["temporal_leakage_detected"] is False
    assert split_meta["spatial_event_leakage_detected"] is False


def test_splitter_event_clustering_prevents_spatial_leakage(splitter):
    # Create 20 records belonging to the same event straddling the train/val boundary
    base_time = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    records = []
    for i in range(50):
        evt_id = "cyclone_remal_cluster" if 30 <= i <= 40 else f"other_evt_{i}"
        records.append(
            TrainingRecord(
                text=f"Weather observation item {i}",
                category=WeatherEventCategory.STRONG_WINDS,
                severity=3,
                timestamp=(base_time + timedelta(hours=i)).isoformat(),
                latitude=22.0,
                longitude=88.0,
                source_type="IMD",
                source_id=f"rep_{i}",
                metadata={"canonical_event_id": evt_id},
            )
        )

    train, val, test, split_meta = splitter.split_chronological(records, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
    
    # Check that cyclone_remal_cluster is NOT split across train and val
    train_clusters = {r.metadata.get("canonical_event_id") for r in train}
    val_clusters = {r.metadata.get("canonical_event_id") for r in val}
    test_clusters = {r.metadata.get("canonical_event_id") for r in test}

    assert not (train_clusters & val_clusters)
    assert not (train_clusters & test_clusters)
    assert not (val_clusters & test_clusters)
    assert split_meta["spatial_event_leakage_detected"] is False


def test_readiness_engine_not_ready_on_insufficient_samples(readiness_engine):
    records = [
        TrainingRecord(
            text="Few rainfall samples",
            category=WeatherEventCategory.RAINFALL,
            severity=2,
            source_type="IMD",
            source_id=f"r_{i}",
        )
        for i in range(10)
    ]
    report = readiness_engine.evaluate_readiness(records)
    assert report.status == DatasetReadiness.NOT_READY
    assert any("Insufficient total samples" in b for b in report.blockers)


def test_readiness_engine_ready_with_warnings(readiness_engine):
    # 200 records with multiple classes but English only and missing Hindi
    records = []
    classes = [
        WeatherEventCategory.RAINFALL,
        WeatherEventCategory.THUNDERSTORM,
        WeatherEventCategory.FLOODING,
        WeatherEventCategory.HEATWAVE,
        WeatherEventCategory.FOG,
    ]
    for i in range(250):
        records.append(
            TrainingRecord(
                text=f"Standard meteorological bulletin record description {i}",
                category=classes[i % len(classes)],
                severity=2,
                source_type="IMD",
                source_id=f"r_{i}",
                language="en",
            )
        )
    report = readiness_engine.evaluate_readiness(records)
    assert report.status == DatasetReadiness.READY_WITH_WARNINGS
    assert report.total_samples == 250
    assert report.overall_score > 0.5


def test_dataset_builder_pipeline_execution(tmp_path, monkeypatch):
    output_dir = str(tmp_path / "datasets")
    builder = SkyPulseDatasetBuilder(output_dir=output_dir, output_version="test_v1")

    # Mock ERA5 processing so unit test remains 100% offline
    monkeypatch.setattr(builder.era5_adapter, "process_era5_training_records", lambda cfg: [])

    # Run build with imd, datagov, skypulse, era5 (gracefully handling missing DB/credentials)
    result = builder.build(
        sources=["imd", "datagov", "skypulse", "era5"],
        start_date="2024-01-01",
        end_date="2024-01-10",
    )

    assert result["status"] == "SUCCESS"
    assert result["version"] == "test_v1"
    assert os.path.exists(os.path.join(result["target_dir"], "dataset_manifest.json"))
    assert os.path.exists(os.path.join(result["target_dir"], "train.jsonl"))
    assert os.path.exists(os.path.join(result["target_dir"], "val.jsonl"))
    assert os.path.exists(os.path.join(result["target_dir"], "test.jsonl"))
    assert os.path.exists(os.path.join(result["target_dir"], "quality_report.json"))
    assert os.path.exists(os.path.join(result["target_dir"], "readiness_report.json"))

    # Validate manifest structure
    with open(os.path.join(result["target_dir"], "dataset_manifest.json"), "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["dataset_version"] == "test_v1"
    assert "sources" in manifest
    assert "source_statuses" in manifest
    assert manifest["source_statuses"]["ERA5"] in ["NOT_CONFIGURED", "NO_DATA", "AVAILABLE"]
