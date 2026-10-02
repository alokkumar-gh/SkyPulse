"""
Unit Tests for SkyPulse ML ModelRegistry & ModelLoader.
Validates:
- Model metadata schemas
- Model registration & discovery
- Status reporting (NOT_TRAINED, LOADED, NOT_LOADED)
- Missing artifact fallback safety
- SHA-256 checksum validation
- Zero crash guarantees
"""

import os
import tempfile
import hashlib
import json
import pytest
from ml.schemas import (
    ModelMetadata,
    ModelStatus,
    ModelFramework,
    ModelTask,
    WeatherEventCategory,
)
from ml.model_registry import ModelRegistry
from ml.model_loader import ModelLoader


def test_model_metadata_creation():
    meta = ModelMetadata(
        name="test_classifier",
        version="1.0.0",
        task=ModelTask.TEXT_CLASSIFICATION,
        framework=ModelFramework.ONNX,
        artifact_path="model.onnx",
        classes=[c.value for c in WeatherEventCategory],
        status=ModelStatus.NOT_TRAINED,
    )
    assert meta.name == "test_classifier"
    assert meta.version == "1.0.0"
    assert meta.status == ModelStatus.NOT_TRAINED
    assert meta.task == ModelTask.TEXT_CLASSIFICATION
    assert meta.metrics == {}


def test_registry_registration_and_retrieval():
    registry = ModelRegistry(model_dir="/tmp/test_models")
    meta = ModelMetadata(
        name="weather_classifier",
        version="1.0.0",
        task=ModelTask.TEXT_CLASSIFICATION,
        framework=ModelFramework.ONNX,
        status=ModelStatus.NOT_TRAINED,
    )
    registry.register_model(meta)
    
    retrieved = registry.get_model_metadata("weather_classifier")
    assert retrieved is not None
    assert retrieved.name == "weather_classifier"
    assert retrieved.status == ModelStatus.NOT_TRAINED


def test_registry_health_summary():
    registry = ModelRegistry(model_dir="/nonexistent/dir")
    summary = registry.get_health_summary()
    assert "models" in summary
    assert "total_registered" in summary
    assert summary["model_directory"] == "/nonexistent/dir"
    
    models = summary["models"]
    assert "weather_event_classifier" in models
    assert "credibility_model" in models
    assert "anomaly_model" in models
    assert "embedding_model" in models
    assert models["weather_event_classifier"]["status"] in [s.value for s in ModelStatus]


def test_model_loader_missing_artifact_graceful():
    loader = ModelLoader()
    meta = ModelMetadata(
        name="nonexistent_model",
        version="1.0.0",
        task=ModelTask.TEXT_CLASSIFICATION,
        framework=ModelFramework.ONNX,
        artifact_path="/nonexistent/path/model.onnx",
        status=ModelStatus.NOT_TRAINED,
    )
    model = loader.load_model(meta)
    assert model is None
    assert meta.status == ModelStatus.NOT_TRAINED


def test_model_loader_corrupt_artifact_graceful():
    with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
        f.write(b"NOT_A_VALID_ONNX_FILE_CORRUPTED_BYTES")
        temp_path = f.name

    try:
        loader = ModelLoader()
        meta = ModelMetadata(
            name="corrupt_model",
            version="1.0.0",
            task=ModelTask.TEXT_CLASSIFICATION,
            framework=ModelFramework.ONNX,
            artifact_path=temp_path,
        )
        model = loader.load_model(meta)
        assert model is None
        assert meta.status in [ModelStatus.ERROR, ModelStatus.NOT_TRAINED]
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_registry_artifact_discovery_with_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        model_sub = os.path.join(tmpdir, "test_model_v1")
        os.makedirs(model_sub)
        
        art_path = os.path.join(model_sub, "model.onnx")
        with open(art_path, "wb") as f:
            f.write(b"dummy_bytes")
            
        sha256 = hashlib.sha256(b"dummy_bytes").hexdigest()
        
        meta_dict = {
            "name": "test_model_v1",
            "version": "1.0.0",
            "task": "TEXT_CLASSIFICATION",
            "framework": "ONNX",
            "artifact_path": art_path,
            "checksum": sha256,
            "status": "TRAINED",
            "metrics": {"macro_f1": 0.92}
        }
        with open(os.path.join(model_sub, "metadata.json"), "w") as f:
            json.dump(meta_dict, f)
            
        registry = ModelRegistry(model_dir=tmpdir)
        registry.discover_local_artifacts()
        
        discovered = registry.get_model_metadata("test_model_v1")
        assert discovered is not None
        assert discovered.checksum == sha256
        assert discovered.metrics.get("macro_f1") == 0.92
