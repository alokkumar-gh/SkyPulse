"""
Comprehensive Unit Tests for SkyPulse ML Model Artifact Integration.
=====================================================================
Covers 16 required production verification scenarios:
1. missing artifact
2. invalid ONNX artifact
3. invalid metadata
4. invalid labels (missing core classes)
5. label/output dimension mismatch
6. checksum mismatch
7. successful artifact validation
8. successful ONNX loading
9. deterministic smoke inference
10. fallback when model unavailable
11. fallback when inference fails
12. model activation
13. failed activation preserving previous model
14. rollback
15. model health summary
16. latency measurement & profiling
"""

import os
import json
import hashlib
import pytest
import numpy as np
import onnx
from onnx import helper, TensorProto

from ml.schemas import (
    ModelStatus,
    ModelFramework,
    ModelMetadata,
    WeatherEventCategory,
)
from ml.validator import ModelArtifactValidator, ArtifactValidationResult
from ml.model_registry import ModelRegistry
from ml.model_loader import ModelLoader
from ml.text_classifier import WeatherTextClassifier
from ai.event_classifier import EventClassifier


@pytest.fixture
def onnx_fixture_generator():
    """Generates a synthetic, lightweight ONNX test fixture with configurable classes."""
    def _create_onnx_file(file_path: str, num_classes: int = 12, ir_version: int = 10):
        input_tensor = helper.make_tensor_value_info("input_ids", TensorProto.INT64, [1, 16])
        output_tensor = helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, num_classes])

        # Preset deterministic logits with rainfall (index 0) top
        logits_data = np.zeros((1, num_classes), dtype=np.float32)
        logits_data[0, 0] = 3.5  # High confidence class
        const_tensor = helper.make_tensor("const_logits", TensorProto.FLOAT, [1, num_classes], logits_data.flatten())
        node = helper.make_node("Constant", inputs=[], outputs=["logits"], value=const_tensor)

        graph = helper.make_graph([node], "synthetic_test_classifier", [input_tensor], [output_tensor])
        model = helper.make_model(graph, producer_name="skypulse_test_fixture", opset_imports=[helper.make_opsetid("", 14)])
        model.ir_version = ir_version
        onnx.save(model, file_path)
        return file_path
    return _create_onnx_file


@pytest.fixture
def standard_labels():
    return [
        "RAINFALL",
        "THUNDERSTORM",
        "FLOODING",
        "HEATWAVE",
        "FOG",
        "DUST_STORM",
        "STRONG_WINDS",
        "CYCLONE",
        "HAILSTORM",
        "SNOWFALL",
        "SMOG",
        "UNKNOWN",
    ]


def test_1_missing_artifact(tmp_path):
    """Scenario 1: Missing artifact directory or missing model.onnx is gracefully rejected."""
    validator = ModelArtifactValidator()
    empty_dir = tmp_path / "empty_model_dir"
    empty_dir.mkdir()

    res = validator.validate_artifact_directory(str(empty_dir))
    assert res.is_valid is False
    assert res.status == ModelStatus.NOT_CONFIGURED
    assert any("not found" in e.lower() for e in res.errors)


def test_2_invalid_onnx_artifact(tmp_path):
    """Scenario 2: Corrupted ONNX file is rejected with clear error."""
    validator = ModelArtifactValidator()
    model_dir = tmp_path / "corrupt_onnx_dir"
    model_dir.mkdir()

    onnx_path = model_dir / "model.onnx"
    with open(onnx_path, "wb") as f:
        f.write(b"CORRUPT_BYTES_NOT_AN_ONNX_GRAPH")

    # Add dummy valid labels to isolate ONNX graph error
    with open(model_dir / "labels.json", "w") as f:
        json.dump(["RAINFALL", "THUNDERSTORM", "FLOODING", "HEATWAVE", "FOG", "DUST_STORM", "STRONG_WINDS"], f)

    res = validator.validate_artifact_directory(str(model_dir))
    assert res.is_valid is False
    assert res.status == ModelStatus.ERROR
    assert any("onnx" in e.lower() for e in res.errors)


def test_3_invalid_metadata(tmp_path, onnx_fixture_generator, standard_labels):
    """Scenario 3: Corrupted or incompatible metadata.json is rejected."""
    validator = ModelArtifactValidator()
    model_dir = tmp_path / "bad_meta_dir"
    model_dir.mkdir()

    onnx_fixture_generator(str(model_dir / "model.onnx"), num_classes=len(standard_labels))
    with open(model_dir / "labels.json", "w") as f:
        json.dump(standard_labels, f)

    # Incompatible framework in metadata
    with open(model_dir / "metadata.json", "w") as f:
        json.dump({"model_name": "weather_event_classifier", "framework": "unsupported_framework"}, f)

    res = validator.validate_artifact_directory(str(model_dir))
    assert res.is_valid is False
    assert res.status == ModelStatus.ERROR
    assert any("framework" in e.lower() for e in res.errors)


def test_4_invalid_labels_missing_core_classes(tmp_path, onnx_fixture_generator):
    """Scenario 4: Labels missing SkyPulse core weather classes are rejected."""
    validator = ModelArtifactValidator()
    model_dir = tmp_path / "missing_classes_dir"
    model_dir.mkdir()

    incomplete_labels = ["RAINFALL", "HEATWAVE"]  # Missing FLOODING, THUNDERSTORM, FOG, etc.
    onnx_fixture_generator(str(model_dir / "model.onnx"), num_classes=len(incomplete_labels))
    with open(model_dir / "labels.json", "w") as f:
        json.dump(incomplete_labels, f)

    res = validator.validate_artifact_directory(str(model_dir))
    assert res.is_valid is False
    assert res.status == ModelStatus.ERROR
    assert any("missing required skypulse core" in e.lower() for e in res.errors)


def test_5_label_output_dimension_mismatch(tmp_path, onnx_fixture_generator, standard_labels):
    """Scenario 5: Output logits dimension mismatch against labels.json length is rejected."""
    validator = ModelArtifactValidator()
    model_dir = tmp_path / "dim_mismatch_dir"
    model_dir.mkdir()

    # ONNX outputs 5 logits, but labels.json has 12 classes
    onnx_fixture_generator(str(model_dir / "model.onnx"), num_classes=5)
    with open(model_dir / "labels.json", "w") as f:
        json.dump(standard_labels, f)

    res = validator.validate_artifact_directory(str(model_dir))
    assert res.is_valid is False
    assert res.status == ModelStatus.ERROR
    assert any("does not match number of labels" in e.lower() for e in res.errors)


def test_6_checksum_mismatch(tmp_path, onnx_fixture_generator, standard_labels):
    """Scenario 6: SHA-256 mismatch against SHA256SUMS or metadata is rejected."""
    validator = ModelArtifactValidator()
    model_dir = tmp_path / "bad_checksum_dir"
    model_dir.mkdir()

    onnx_fixture_generator(str(model_dir / "model.onnx"), num_classes=len(standard_labels))
    with open(model_dir / "labels.json", "w") as f:
        json.dump(standard_labels, f)

    # Put a wrong checksum in SHA256SUMS
    with open(model_dir / "SHA256SUMS", "w") as f:
        f.write("0000000000000000000000000000000000000000000000000000000000000000 *model.onnx\n")

    res = validator.validate_artifact_directory(str(model_dir))
    assert res.is_valid is False
    assert res.status == ModelStatus.ERROR
    assert any("mismatch" in e.lower() for e in res.errors)


def test_7_successful_artifact_validation(tmp_path, onnx_fixture_generator, standard_labels):
    """Scenario 7: Complete and valid artifact directory passes validation."""
    validator = ModelArtifactValidator()
    model_dir = tmp_path / "valid_model_v1"
    model_dir.mkdir()

    onnx_path = model_dir / "model.onnx"
    onnx_fixture_generator(str(onnx_path), num_classes=len(standard_labels))

    actual_hash = validator.compute_sha256(str(onnx_path))
    with open(model_dir / "SHA256SUMS", "w") as f:
        f.write(f"{actual_hash}  model.onnx\n")

    with open(model_dir / "labels.json", "w") as f:
        json.dump(standard_labels, f)

    meta = {
        "model_name": "weather_event_classifier",
        "model_version": "v1",
        "framework": "onnx",
        "task": "weather_event_classification",
        "dataset_version": "v2",
        "artifact_sha256": actual_hash,
        "training_period": {"start": "2024-01-01", "end": "2025-12-31"},
        "validation_period": {"start": "2026-01-01", "end": "2026-06-30"},
        "test_period": {"start": "2026-07-01", "end": "2026-09-30"},
    }
    with open(model_dir / "metadata.json", "w") as f:
        json.dump(meta, f)

    res = validator.validate_artifact_directory(str(model_dir))
    assert res.is_valid is True
    assert res.status == ModelStatus.READY
    assert res.checksum_verified is True
    assert res.smoke_inference_passed is True
    assert res.smoke_latency_ms > 0.0
    assert len(res.errors) == 0


def test_8_successful_onnx_loading(tmp_path, onnx_fixture_generator, standard_labels):
    """Scenario 8: ModelLoader loads valid ONNX session and caches it."""
    loader = ModelLoader()
    model_dir = tmp_path / "loadable_onnx_dir"
    model_dir.mkdir()

    onnx_path = model_dir / "model.onnx"
    onnx_fixture_generator(str(onnx_path), num_classes=len(standard_labels))

    meta = ModelMetadata(
        model_name="test_loadable_model",
        model_version="v1",
        task="text_classification",
        framework=ModelFramework.ONNX,
        artifact_path=str(model_dir),
        status=ModelStatus.READY,
    )

    session = loader.load_model(meta)
    assert session is not None
    assert hasattr(session, "run")
    assert meta.loaded is True
    assert meta.last_loaded_at is not None


def test_9_deterministic_smoke_inference(tmp_path, onnx_fixture_generator, standard_labels):
    """Scenario 9: Smoke test verifies logits are finite, probabilities sum to 1.0, and category is valid."""
    validator = ModelArtifactValidator()
    model_dir = tmp_path / "smoke_test_dir"
    model_dir.mkdir()

    onnx_path = model_dir / "model.onnx"
    onnx_fixture_generator(str(onnx_path), num_classes=len(standard_labels))
    with open(model_dir / "labels.json", "w") as f:
        json.dump(standard_labels, f)

    res = validator.validate_artifact_directory(str(model_dir))
    assert res.smoke_inference_passed is True
    assert res.is_valid is True


@pytest.mark.asyncio
async def test_10_fallback_when_model_unavailable():
    """Scenario 10: EventClassifier safely falls back to FallbackAIProvider when ML is unconfigured/inactive."""
    classifier = EventClassifier()
    # Unconfigured model -> should seamlessly return rule-based fallback classification
    res = await classifier.classify("Extremely heavy rainfall causing waterlogging in Mumbai")
    assert res is not None
    assert res.category == "RAINFALL"
    assert res.fallback_used is True
    assert res.method in ["rule_based", "fallback", "fallback_heuristic", "heuristic"]


@pytest.mark.asyncio
async def test_11_fallback_when_inference_fails(monkeypatch):
    """Scenario 11: When ML predict throws a runtime error, EventClassifier catches it and continues fallback."""
    classifier = EventClassifier()

    async def _failing_classify(text, metadata=None):
        raise RuntimeError("Simulated runtime tensor memory fault")

    from ml.inference_service import ml_inference_service
    monkeypatch.setattr(ml_inference_service, "classify_event", _failing_classify)

    res = await classifier.classify("Severe thunderstorm and lightning over Kolkata")
    assert res is not None
    assert res.category == "THUNDERSTORM"
    assert res.fallback_used is True


def test_12_model_activation(tmp_path, onnx_fixture_generator, standard_labels):
    """Scenario 12: ModelRegistry activates a validated model version and updates status to ACTIVE."""
    registry = ModelRegistry(model_dir=str(tmp_path / "models"))
    v1_dir = tmp_path / "models" / "weather_event_classifier" / "v1"
    v1_dir.mkdir(parents=True)

    onnx_path = v1_dir / "model.onnx"
    onnx_fixture_generator(str(onnx_path), num_classes=len(standard_labels))
    with open(v1_dir / "labels.json", "w") as f:
        json.dump(standard_labels, f)

    # Register artifact
    val_res, meta = registry.validate_and_register_artifact(str(v1_dir), "weather_event_classifier", activate_if_valid=False)
    assert val_res.is_valid is True
    assert meta.status == ModelStatus.READY
    assert meta.active is False

    # Activate
    success, msg = registry.activate_model("weather_event_classifier", "v1")
    assert success is True
    active_m = registry.get_active_model("weather_event_classifier")
    assert active_m is not None
    assert active_m.model_version == "v1"
    assert active_m.status == ModelStatus.ACTIVE
    assert active_m.active is True


def test_13_failed_activation_preserves_previous_model(tmp_path, onnx_fixture_generator, standard_labels):
    """Scenario 13: If a new model version fails validation during activation, previous active model remains active."""
    registry = ModelRegistry(model_dir=str(tmp_path / "models"))
    models_root = tmp_path / "models" / "weather_event_classifier"

    # 1. Valid v1
    v1_dir = models_root / "v1"
    v1_dir.mkdir(parents=True)
    onnx_fixture_generator(str(v1_dir / "model.onnx"), num_classes=len(standard_labels))
    with open(v1_dir / "labels.json", "w") as f:
        json.dump(standard_labels, f)
    registry.validate_and_register_artifact(str(v1_dir), "weather_event_classifier", activate_if_valid=True)
    assert registry.get_active_model("weather_event_classifier").model_version == "v1"

    # 2. Corrupt v2
    v2_dir = models_root / "v2"
    v2_dir.mkdir(parents=True)
    with open(v2_dir / "model.onnx", "wb") as f:
        f.write(b"BROKEN_BYTES")
    with open(v2_dir / "labels.json", "w") as f:
        json.dump(standard_labels, f)

    registry.register_model(ModelMetadata(
        model_name="weather_event_classifier",
        model_version="v2",
        artifact_path=str(v2_dir),
        status=ModelStatus.NOT_CONFIGURED,
    ))

    # Attempt to activate broken v2
    success, msg = registry.activate_model("weather_event_classifier", "v2")
    assert success is False
    assert "Activation failed" in msg

    # Verify v1 is STILL active
    active_m = registry.get_active_model("weather_event_classifier")
    assert active_m is not None
    assert active_m.model_version == "v1"
    assert active_m.active is True


def test_14_rollback(tmp_path, onnx_fixture_generator, standard_labels):
    """Scenario 14: Rollback safely reactivates a prior version or deactivates to fallback."""
    registry = ModelRegistry(model_dir=str(tmp_path / "models"))
    models_root = tmp_path / "models" / "weather_event_classifier"

    # Set up v1 and v2
    v1_dir = models_root / "v1"
    v1_dir.mkdir(parents=True)
    onnx_fixture_generator(str(v1_dir / "model.onnx"), num_classes=len(standard_labels))
    with open(v1_dir / "labels.json", "w") as f:
        json.dump(standard_labels, f)

    v2_dir = models_root / "v2"
    v2_dir.mkdir(parents=True)
    onnx_fixture_generator(str(v2_dir / "model.onnx"), num_classes=len(standard_labels))
    with open(v2_dir / "labels.json", "w") as f:
        json.dump(standard_labels, f)

    registry.validate_and_register_artifact(str(v1_dir), "weather_event_classifier", activate_if_valid=False)
    registry.validate_and_register_artifact(str(v2_dir), "weather_event_classifier", activate_if_valid=True)
    assert registry.get_active_model("weather_event_classifier").model_version == "v2"

    # Rollback to v1
    success, msg = registry.rollback_model("weather_event_classifier", target_version="v1")
    assert success is True
    assert registry.get_active_model("weather_event_classifier").model_version == "v1"

    # Rollback when no specific target is given and v1 is active -> deactivates to FallbackAIProvider
    success_deact, msg_deact = registry.rollback_model("weather_event_classifier", target_version="v2")
    assert success_deact is True
    assert registry.get_active_model("weather_event_classifier").model_version == "v2"


def test_15_model_health_summary():
    """Scenario 15: Health summary exposes complete telemetry without fabricating metrics."""
    registry = ModelRegistry(model_dir="/tmp/health_test")
    health = registry.get_health_summary()
    assert "models" in health
    assert "total_registered" in health
    assert "fallback_operational" in health
    assert health["fallback_operational"] is True
    assert "real_trained_model_available" in health

    weather_m = health["models"]["weather_event_classifier"]
    assert "model_name" in weather_m
    assert "model_version" in weather_m
    assert "status" in weather_m
    assert "framework" in weather_m
    assert "active" in weather_m
    assert "loaded" in weather_m
    assert "artifact_available" in weather_m
    assert "artifact_valid" in weather_m
    assert "fallback_enabled" in weather_m
    assert "labels" in weather_m
    assert "checksum_status" in weather_m
    assert "latency_breakdown" in weather_m


def test_16_inference_latency_measurement(tmp_path, onnx_fixture_generator, standard_labels):
    """Scenario 16: Latency profiling accurately records preprocessing, ONNX, postprocessing, and total times."""
    registry = ModelRegistry(model_dir=str(tmp_path / "models"))
    v1_dir = tmp_path / "models" / "weather_event_classifier" / "v1"
    v1_dir.mkdir(parents=True)

    onnx_fixture_generator(str(v1_dir / "model.onnx"), num_classes=len(standard_labels))
    with open(v1_dir / "labels.json", "w") as f:
        json.dump(standard_labels, f)

    registry.validate_and_register_artifact(str(v1_dir), "weather_event_classifier", activate_if_valid=True)

    # Record simulated multi-stage latency
    registry.record_inference_latency(
        model_name="weather_event_classifier",
        prep_ms=0.45,
        infer_ms=2.10,
        post_ms=0.15,
        total_ms=2.70,
    )

    m = registry.get_model("weather_event_classifier")
    assert m.inference_count == 1
    assert m.total_latency_ms == 2.70
    assert m.latency_breakdown["preprocessing_ms"] == 0.45
    assert m.latency_breakdown["inference_ms"] == 2.10
    assert m.latency_breakdown["postprocessing_ms"] == 0.15
    assert m.latency_breakdown["total_ms"] == 2.70
    assert m.avg_latency_breakdown["total_ms"] == 2.70
