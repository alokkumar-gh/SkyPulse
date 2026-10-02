"""
SkyPulse Lazy Model Loader
==========================
Safely loads machine learning models (ONNX, PyTorch, Scikit-Learn, SentenceTransformers).
Ensures zero-crash resiliency: missing artifacts or dependencies gracefully return None.
"""

import os
import logging
from typing import Any, Optional, Dict
from datetime import datetime, timezone

from ml.schemas import ModelStatus, ModelFramework
from ml.model_registry import model_registry

logger = logging.getLogger("skypulse.ml.loader")


class ModelLoader:
    """
    Lazy loader for machine learning artifacts.
    Loads models into memory only when needed, caching loaded sessions for high-speed inference.
    """

    def __init__(self):
        self._loaded_models: Dict[str, Any] = {}

    def unload_model(self, model_name: str) -> None:
        """Removes a model instance from loaded cache."""
        self._loaded_models.pop(model_name, None)

    def load_model(self, model_name_or_meta: Any, version: Optional[str] = None) -> Optional[Any]:
        """
        Retrieves a loaded model instance. If not yet loaded, attempts to load
        the artifact from disk according to its registered framework.
        """
        if isinstance(model_name_or_meta, str):
            model_name = model_name_or_meta
            metadata = model_registry.get_model(model_name, version=version)
        elif hasattr(model_name_or_meta, "model_name") or hasattr(model_name_or_meta, "name"):
            metadata = model_name_or_meta
            model_name = getattr(metadata, "model_name", None) or getattr(metadata, "name", "unknown")
            model_registry.register_model(metadata)
        else:
            return None

        cache_key = f"{model_name}:{version}" if version else model_name
        if cache_key in self._loaded_models:
            return self._loaded_models[cache_key]

        if not metadata:
            logger.warning("Attempted to load unregistered model '%s'", model_name)
            return None

        if metadata.status in [ModelStatus.NOT_CONFIGURED, ModelStatus.DISABLED]:
            # Check if artifact path actually exists on disk
            if not metadata.artifact_path or not os.path.exists(metadata.artifact_path):
                return None

        artifact_path = metadata.artifact_path
        if not artifact_path or not os.path.exists(artifact_path):
            if metadata.status not in [ModelStatus.NOT_TRAINED, ModelStatus.NOT_CONFIGURED]:
                model_registry.update_status(model_name, ModelStatus.NOT_CONFIGURED, version=version)
            metadata.loaded = False
            return None

        try:
            loaded_instance = None
            if metadata.framework == ModelFramework.ONNX:
                loaded_instance = self._load_onnx_model(artifact_path)
            elif metadata.framework == ModelFramework.PYTORCH:
                loaded_instance = self._load_pytorch_model(artifact_path)
            elif metadata.framework == ModelFramework.SCIKIT_LEARN:
                loaded_instance = self._load_scikit_model(artifact_path)
            elif metadata.framework == ModelFramework.HUGGINGFACE:
                loaded_instance = self._load_huggingface_model(artifact_path)

            if loaded_instance is not None:
                self._loaded_models[cache_key] = loaded_instance
                metadata.loaded = True
                metadata.last_loaded_at = datetime.now(timezone.utc)
                if metadata.status not in [ModelStatus.ACTIVE, ModelStatus.ERROR]:
                    model_registry.update_status(model_name, ModelStatus.LOADED, version=version)
                logger.info("Successfully loaded model '%s' [%s]", model_name, metadata.framework.value if hasattr(metadata.framework, "value") else metadata.framework)
                return loaded_instance
            else:
                metadata.loaded = False
                metadata.status = ModelStatus.ERROR
                model_registry.update_status(model_name, ModelStatus.ERROR, error="Failed to load artifact", version=version)
                return None

        except Exception as e:
            logger.error("Failed to load model '%s': %s", model_name, e)
            metadata.loaded = False
            model_registry.update_status(model_name, ModelStatus.ERROR, error=str(e), version=version)
            return None

    @staticmethod
    def _load_onnx_model(path: str) -> Optional[Any]:
        """Loads an ONNX Runtime InferenceSession for CPU inference."""
        try:
            import onnxruntime as ort
            onnx_file = path
            if os.path.isdir(path):
                candidate = os.path.join(path, "model.onnx")
                if os.path.exists(candidate):
                    onnx_file = candidate
                else:
                    for f in os.listdir(path):
                        if f.endswith(".onnx"):
                            onnx_file = os.path.join(path, f)
                            break
            if not os.path.isfile(onnx_file):
                return None
            sess_options = ort.SessionOptions()
            sess_options.intra_op_num_threads = 2
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            session = ort.InferenceSession(onnx_file, sess_options, providers=["CPUExecutionProvider"])
            return session
        except ImportError:
            logger.debug("onnxruntime not installed; ONNX model loading skipped.")
            return None
        except Exception as e:
            logger.warning("Could not initialize ONNX session at %s: %s", path, e)
            return None

    @staticmethod
    def _load_pytorch_model(path: str) -> Optional[Any]:
        """Loads PyTorch model weights on CPU."""
        try:
            import torch
            pt_file = path
            if os.path.isdir(path):
                for f in os.listdir(path):
                    if f.endswith((".pt", ".pth", ".bin")):
                        pt_file = os.path.join(path, f)
                        break
            if not os.path.isfile(pt_file):
                return None
            model = torch.load(pt_file, map_location=torch.device("cpu"), weights_only=True)
            model.eval()
            return model
        except ImportError:
            logger.debug("torch not installed; PyTorch model loading skipped.")
            return None
        except Exception as e:
            logger.warning("Could not load PyTorch weights from %s: %s", path, e)
            return None

    @staticmethod
    def _load_scikit_model(path: str) -> Optional[Any]:
        """Loads a Scikit-Learn model via joblib."""
        try:
            import joblib
            pkl_file = path
            if os.path.isdir(path):
                for f in os.listdir(path):
                    if f.endswith((".joblib", ".pkl")):
                        pkl_file = os.path.join(path, f)
                        break
            if not os.path.isfile(pkl_file):
                return None
            return joblib.load(pkl_file)
        except ImportError:
            logger.debug("joblib not installed; scikit-learn model loading skipped.")
            return None
        except Exception as e:
            logger.warning("Could not load Scikit-Learn model from %s: %s", path, e)
            return None

    @staticmethod
    def _load_huggingface_model(path: str) -> Optional[Any]:
        """Loads a SentenceTransformer model."""
        try:
            from sentence_transformers import SentenceTransformer
            return SentenceTransformer(path)
        except ImportError:
            logger.debug("sentence_transformers not installed; HF model loading skipped.")
            return None
        except Exception as e:
            logger.warning("Could not load SentenceTransformer from %s: %s", path, e)
            return None


# Global loader instance
model_loader = ModelLoader()
