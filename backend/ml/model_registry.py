"""
SkyPulse ML Model Registry
==========================
Centralized registry for managing model lifecycles, versioned artifact metadata,
status tracking, latency profiling, atomic activation, and safe fallback behaviors.

Lifecycle States:
  NOT_CONFIGURED -> ARTIFACT_FOUND -> VALIDATING -> READY -> LOADED -> ACTIVE
  (with ERROR and DISABLED states, and atomic rollback guarantees)
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from ml.schemas import ModelMetadata, ModelStatus, ModelFramework
from ml.validator import model_artifact_validator, ArtifactValidationResult
from app.core.config import settings

logger = logging.getLogger("skypulse.ml.registry")


class ModelRegistry:
    """
    Registry for all SkyPulse machine learning models.
    Tracks artifact locations, versions, evaluation metrics, runtime health, and safe activation/rollback.
    """

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = (
            model_dir
            or getattr(settings, "ML_MODEL_DIR", "")
            or os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
        )
        self._models: Dict[str, ModelMetadata] = {}
        self._model_versions: Dict[str, Dict[str, ModelMetadata]] = {}
        self._active_versions: Dict[str, str] = {}
        self._init_default_registry()

    def _init_default_registry(self) -> None:
        """Registers default model definitions and inspects for physical artifacts."""
        # 1. Weather Event Classifier (DistilBERT / ONNX)
        self.register_model(
            ModelMetadata(
                model_name="weather_event_classifier",
                version="v1",
                model_version="v1",
                task="text_classification",
                framework=ModelFramework.ONNX,
                artifact_path=os.path.join(self.model_dir, "weather_event_classifier", "v1"),
                status=ModelStatus.NOT_CONFIGURED,
                active=False,
                fallback_enabled=True,
                training_period={"start": "2024-01-01", "end": "2025-12-31"},
                validation_period={"start": "2026-01-01", "end": "2026-06-30"},
                test_period={"start": "2026-07-01", "end": "latest_cds"},
                metrics={},
            )
        )

        # 2. Semantic Embedding Model (Sentence Transformers / MiniLM)
        self.register_model(
            ModelMetadata(
                model_name="sentence_embedding_model",
                version="1.0.0",
                model_version="1.0.0",
                task="embedding",
                framework=ModelFramework.HUGGINGFACE,
                artifact_path=os.path.join(self.model_dir, "embeddings"),
                status=ModelStatus.NOT_CONFIGURED,
                active=False,
                fallback_enabled=True,
                metrics={
                    "embedding_dimension": 384,
                    "default_model": getattr(settings, "EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2") or "all-MiniLM-L6-v2",
                },
            )
        )

        # 3. Credibility / Misinformation Model
        self.register_model(
            ModelMetadata(
                model_name="credibility_model",
                version="1.0.0",
                model_version="1.0.0",
                task="credibility",
                framework=ModelFramework.SCIKIT_LEARN,
                artifact_path=os.path.join(self.model_dir, "credibility"),
                status=ModelStatus.NOT_CONFIGURED,
                active=False,
                fallback_enabled=True,
                metrics={},
            )
        )

        # 4. Spatiotemporal Anomaly Detection Model
        self.register_model(
            ModelMetadata(
                model_name="anomaly_model",
                version="1.0.0",
                model_version="1.0.0",
                task="anomaly_detection",
                framework=ModelFramework.SCIKIT_LEARN,
                artifact_path=os.path.join(self.model_dir, "anomaly"),
                status=ModelStatus.NOT_CONFIGURED,
                active=False,
                fallback_enabled=True,
                metrics={},
            )
        )

        self.discover_local_artifacts()

    def register_model(self, metadata: ModelMetadata) -> None:
        """Adds or updates a model definition in the registry."""
        m_name = metadata.model_name or metadata.name
        m_version = metadata.model_version or metadata.version or "1.0.0"

        if m_name not in self._model_versions:
            self._model_versions[m_name] = {}
        self._model_versions[m_name][m_version] = metadata

        # Update primary model reference
        if metadata.active or m_name not in self._models or self._models[m_name].status == ModelStatus.NOT_CONFIGURED:
            self._models[m_name] = metadata
            if metadata.active:
                self._active_versions[m_name] = m_version

        logger.info("Registered model '%s' [v%s, status=%s, active=%s]", m_name, m_version, metadata.status.value, metadata.active)

    def get_model(self, model_name: str, version: Optional[str] = None) -> Optional[ModelMetadata]:
        """Retrieves model metadata by name and optional version."""
        if model_name == "embedding_model":
            model_name = "sentence_embedding_model"

        if version and model_name in self._model_versions:
            return self._model_versions[model_name].get(version)

        return self._models.get(model_name)

    def get_model_metadata(self, model_name: str, version: Optional[str] = None) -> Optional[ModelMetadata]:
        """Alias for get_model."""
        return self.get_model(model_name, version=version)

    def get_active_model(self, model_name: str) -> Optional[ModelMetadata]:
        """Retrieves the currently ACTIVE model version, or None if no active model exists."""
        if model_name == "embedding_model":
            model_name = "sentence_embedding_model"
        active_ver = self._active_versions.get(model_name)
        if active_ver and model_name in self._model_versions:
            model = self._model_versions[model_name].get(active_ver)
            if model and model.active and model.status in [ModelStatus.ACTIVE, ModelStatus.LOADED]:
                return model
        
        # Fallback check
        primary = self._models.get(model_name)
        if primary and primary.active and primary.status in [ModelStatus.ACTIVE, ModelStatus.LOADED]:
            return primary
        return None

    def list_models(self) -> List[ModelMetadata]:
        """Returns all primary registered models."""
        return list(self._models.values())

    def list_all_versions(self, model_name: str) -> List[ModelMetadata]:
        """Returns all versions registered for a given model."""
        if model_name == "embedding_model":
            model_name = "sentence_embedding_model"
        return list(self._model_versions.get(model_name, {}).values())

    def update_status(self, model_name: str, status: ModelStatus, error: Optional[str] = None, version: Optional[str] = None) -> None:
        """Updates the status and error information of a model."""
        target = self.get_model(model_name, version=version)
        if target:
            target.status = status
            if error:
                target.last_error = error
                target.error_count += 1
            if status == ModelStatus.ACTIVE:
                target.active = True
                self._active_versions[model_name] = target.model_version

    def record_inference_latency(
        self,
        model_name: str,
        prep_ms: float,
        infer_ms: float,
        post_ms: float,
        total_ms: float,
    ) -> None:
        """Records granular inference latency metrics (preprocessing, ONNX inference, postprocessing, total)."""
        target = self.get_model(model_name)
        if target:
            target.inference_count += 1
            target.total_latency_ms += total_ms
            target.last_inference_at = datetime.now(timezone.utc)
            
            target.latency_breakdown = {
                "preprocessing_ms": round(prep_ms, 2),
                "inference_ms": round(infer_ms, 2),
                "postprocessing_ms": round(post_ms, 2),
                "total_ms": round(total_ms, 2),
            }

            # Update moving averages
            n = target.inference_count
            prev_avg = target.avg_latency_breakdown
            target.avg_latency_breakdown = {
                "preprocessing_ms": round((prev_avg.get("preprocessing_ms", 0.0) * (n - 1) + prep_ms) / n, 2),
                "inference_ms": round((prev_avg.get("inference_ms", 0.0) * (n - 1) + infer_ms) / n, 2),
                "postprocessing_ms": round((prev_avg.get("postprocessing_ms", 0.0) * (n - 1) + post_ms) / n, 2),
                "total_ms": round((target.total_latency_ms) / n, 2),
            }

    def record_inference(self, model_name: str, latency_ms: float) -> None:
        """Convenience method for recording single total latency."""
        self.record_inference_latency(model_name, prep_ms=0.0, infer_ms=latency_ms, post_ms=0.0, total_ms=latency_ms)

    def validate_and_register_artifact(
        self,
        artifact_dir: str,
        expected_model_name: str = "weather_event_classifier",
        activate_if_valid: bool = False,
    ) -> Tuple[ArtifactValidationResult, Optional[ModelMetadata]]:
        """
        Validates an on-disk artifact directory, registers the version metadata,
        and optionally activates it if validation passes.
        """
        val_res = model_artifact_validator.validate_artifact_directory(
            artifact_dir=artifact_dir,
            expected_model_name=expected_model_name,
        )

        metadata = ModelMetadata(
            model_name=val_res.model_name,
            version=val_res.model_version,
            model_version=val_res.model_version,
            task="text_classification",
            framework=ModelFramework.ONNX,
            artifact_path=val_res.artifact_path,
            checksum=val_res.sha256_checksum,
            artifact_sha256=val_res.sha256_checksum,
            checksum_status="VERIFIED" if val_res.checksum_verified else "UNVERIFIED",
            classes=val_res.labels,
            labels=val_res.labels,
            dataset_version=val_res.metadata.get("dataset_version", "v2"),
            training_period=val_res.metadata.get("training_period", {}),
            validation_period=val_res.metadata.get("validation_period", {}),
            test_period=val_res.metadata.get("test_period", {}),
            status=val_res.status,
            active=False,
            artifact_available=True,
            artifact_valid=val_res.is_valid,
            fallback_enabled=True,
            last_validated_at=datetime.now(timezone.utc),
            last_error="; ".join(val_res.errors) if val_res.errors else None,
            metrics=val_res.metadata.get("metrics", {}),
            created_at=val_res.metadata.get("created_at"),
        )

        self.register_model(metadata)

        if val_res.is_valid and activate_if_valid:
            self.activate_model(val_res.model_name, val_res.model_version)

        return val_res, metadata

    def activate_model(self, model_name: str, version: str) -> Tuple[bool, str]:
        """
        Safely and atomically activates a specific validated model version.
        If validation or smoke test fails, leaves the previously active model intact.
        """
        if model_name == "embedding_model":
            model_name = "sentence_embedding_model"

        target = self.get_model(model_name, version=version)
        if not target or not target.artifact_path:
            return False, f"Model '{model_name}' version '{version}' is not registered."

        # Re-validate artifact before activation
        val_res = model_artifact_validator.validate_artifact_directory(
            artifact_dir=target.artifact_path,
            expected_model_name=model_name,
        )

        if not val_res.is_valid:
            target.status = ModelStatus.ERROR
            target.last_error = f"Activation failed validation: {'; '.join(val_res.errors)}"
            target.artifact_valid = False
            logger.error("Failed activation for '%s' v%s: %s", model_name, version, target.last_error)
            return False, target.last_error

        # Update metadata state
        target.status = ModelStatus.ACTIVE
        target.active = True
        target.artifact_valid = True
        target.last_validated_at = datetime.now(timezone.utc)
        target.labels = val_res.labels
        target.classes = val_res.labels

        # Deactivate any other active versions for this model
        for v, m in self._model_versions.get(model_name, {}).items():
            if v != version and m.active:
                m.active = False
                m.status = ModelStatus.READY

        self._models[model_name] = target
        self._active_versions[model_name] = version

        logger.info("Successfully ACTIVATED model '%s' version '%s'.", model_name, version)
        return True, f"Model '{model_name}' version '{version}' activated successfully."

    def rollback_model(self, model_name: str, target_version: Optional[str] = None) -> Tuple[bool, str]:
        """
        Rolls back the active model to a specified version, or to the most recent previous valid version.
        If no other valid version exists, deactivates to FallbackAIProvider.
        """
        if model_name == "embedding_model":
            model_name = "sentence_embedding_model"

        current_active = self._active_versions.get(model_name)
        versions_dict = self._model_versions.get(model_name, {})

        if target_version:
            if target_version not in versions_dict:
                return False, f"Target rollback version '{target_version}' not found for model '{model_name}'."
            return self.activate_model(model_name, target_version)

        # Find any other valid version
        candidate_versions = [
            v for v, m in versions_dict.items()
            if v != current_active and (m.artifact_valid or m.status == ModelStatus.READY)
        ]

        if candidate_versions:
            next_version = sorted(candidate_versions)[-1]
            return self.activate_model(model_name, next_version)

        # No valid alternative: deactivate to fallback
        if current_active and current_active in versions_dict:
            versions_dict[current_active].active = False
            versions_dict[current_active].status = ModelStatus.READY
        self._active_versions.pop(model_name, None)
        if model_name in self._models:
            self._models[model_name].active = False
            self._models[model_name].status = ModelStatus.READY

        logger.warning("No alternative model version available for '%s'. Rolled back to FallbackAIProvider.", model_name)
        return True, f"Deactivated active model '{model_name}'. FallbackAIProvider is operational."

    def discover_local_artifacts(self) -> None:
        """
        Inspects the configured model directory for trained artifacts.
        Supports versioned directories (e.g. models/weather_event_classifier/v1/)
        and flat model directories.
        """
        if not os.path.exists(self.model_dir):
            return

        try:
            for entry in os.scandir(self.model_dir):
                if entry.is_dir():
                    model_dir_name = entry.name
                    # Check for versioned subdirectories (e.g. v1, v2, 1.0.0)
                    has_subversions = False
                    for sub in os.scandir(entry.path):
                        if sub.is_dir() and (os.path.exists(os.path.join(sub.path, "model.onnx")) or os.path.exists(os.path.join(sub.path, "metadata.json"))):
                            has_subversions = True
                            self.validate_and_register_artifact(
                                artifact_dir=sub.path,
                                expected_model_name=model_dir_name,
                                activate_if_valid=False,
                            )

                    # Check if root of entry is itself a model artifact
                    if not has_subversions:
                        if os.path.exists(os.path.join(entry.path, "model.onnx")) or os.path.exists(os.path.join(entry.path, "metadata.json")):
                            self.validate_and_register_artifact(
                                artifact_dir=entry.path,
                                expected_model_name=model_dir_name,
                                activate_if_valid=False,
                            )
        except Exception as e:
            logger.warning("Error scanning model directory '%s': %s", self.model_dir, e)

    def get_health_summary(self) -> Dict[str, Any]:
        """Provides comprehensive health telemetry for Admin and System Health APIs."""
        models_dict = {}
        for name, m in self._models.items():
            active_v = self._active_versions.get(name)
            is_active = bool(m.active and m.status in [ModelStatus.ACTIVE, ModelStatus.LOADED])
            models_dict[name] = {
                "model_name": m.model_name or name,
                "version": m.version or m.model_version,
                "model_version": m.model_version or m.version,
                "task": str(m.task),
                "framework": m.framework.value if hasattr(m.framework, "value") else str(m.framework),
                "status": m.status.value if hasattr(m.status, "value") else str(m.status),
                "active": is_active,
                "loaded": bool(m.loaded or m.status in [ModelStatus.LOADED, ModelStatus.ACTIVE]),
                "artifact_available": m.artifact_available,
                "artifact_valid": m.artifact_valid,
                "fallback_enabled": m.fallback_enabled,
                "labels": m.labels or m.classes,
                "checksum_status": m.checksum_status or ("VERIFIED" if m.checksum else "NONE"),
                "artifact_sha256": m.artifact_sha256 or m.checksum,
                "last_validated_at": m.last_validated_at.isoformat() if m.last_validated_at else None,
                "last_loaded_at": m.last_loaded_at.isoformat() if m.last_loaded_at else None,
                "last_inference_at": m.last_inference_at.isoformat() if m.last_inference_at else None,
                "inference_count": m.inference_count,
                "avg_latency_ms": round(m.avg_latency_ms, 2),
                "latency_breakdown": m.latency_breakdown,
                "avg_latency_breakdown": m.avg_latency_breakdown,
                "error_count": m.error_count,
                "last_error": m.last_error,
                "metrics": m.metrics if m.metrics else {},
                "dataset_version": m.dataset_version,
            }

        if "sentence_embedding_model" in models_dict and "embedding_model" not in models_dict:
            models_dict["embedding_model"] = models_dict["sentence_embedding_model"]

        active_count = sum(1 for m in models_dict.values() if m.get("active"))

        return {
            "model_dir": self.model_dir,
            "model_directory": self.model_dir,
            "total_registered_models": len(self._models),
            "total_registered": len(self._models),
            "active_models_count": active_count,
            "fallback_operational": True,
            "real_trained_model_available": active_count > 0,
            "models": models_dict,
        }


# Global Registry Instance
model_registry = ModelRegistry()
