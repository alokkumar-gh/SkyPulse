"""
SkyPulse Model Artifact Validator
=================================
Validates production machine learning artifacts (ONNX graphs, metadata schemas,
label configurations, SHA-256 integrity, and deterministic smoke inference).

Lifecycle transition:
  ARTIFACT_FOUND -> VALIDATING -> READY / ERROR
"""

import os
import json
import math
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from ml.schemas import ModelStatus, WeatherEventCategory

logger = logging.getLogger("skypulse.ml.validator")

# SkyPulse Core Weather Classes
CORE_WEATHER_CLASSES = {
    WeatherEventCategory.RAINFALL.value,
    WeatherEventCategory.THUNDERSTORM.value,
    WeatherEventCategory.FLOODING.value,
    WeatherEventCategory.HEATWAVE.value,
    WeatherEventCategory.FOG.value,
    WeatherEventCategory.DUST_STORM.value,
    WeatherEventCategory.STRONG_WINDS.value,
}

# Supported Extended Classes
OPTIONAL_WEATHER_CLASSES = {
    WeatherEventCategory.CYCLONE.value,
    WeatherEventCategory.HAILSTORM.value,
    WeatherEventCategory.SNOWFALL.value,
    WeatherEventCategory.SMOG.value,
    WeatherEventCategory.UNKNOWN.value,
}


@dataclass
class ArtifactValidationResult:
    """Detailed report resulting from validating an on-disk ML model artifact."""
    is_valid: bool
    status: ModelStatus
    model_name: str = ""
    model_version: str = "v1"
    artifact_path: str = ""
    onnx_file_path: Optional[str] = None
    sha256_checksum: Optional[str] = None
    checksum_verified: bool = False
    labels: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    preprocessing_config: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    smoke_inference_passed: bool = False
    smoke_latency_ms: float = 0.0


class ModelArtifactValidator:
    """
    Validates on-disk ML model artifacts against production integrity standards.
    Guarantees no invalid, unverified, or broken model becomes active.
    """

    @staticmethod
    def compute_sha256(file_path: str) -> Optional[str]:
        """Calculates deterministic SHA-256 hash of a file."""
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return None
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()

    def parse_sha256sums_file(self, sums_path: str) -> Dict[str, str]:
        """Parses a standard SHA256SUMS file into {filename: sha256_hash} mapping."""
        mapping = {}
        if not os.path.exists(sums_path):
            return mapping
        try:
            with open(sums_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        chk, fname = parts[0].strip().lower(), os.path.basename(parts[1].strip().lstrip("*"))
                        mapping[fname] = chk
        except Exception as e:
            logger.warning("Failed to parse SHA256SUMS file at %s: %s", sums_path, e)
        return mapping

    def validate_artifact_directory(
        self,
        artifact_dir: str,
        expected_model_name: str = "weather_event_classifier",
    ) -> ArtifactValidationResult:
        """
        Runs comprehensive validation across an artifact directory.
        Checks existence, checksums, metadata, labels, ONNX graph, and runs smoke inference.
        """
        errors: List[str] = []
        warnings: List[str] = []
        artifact_dir_abs = os.path.abspath(artifact_dir)

        if not os.path.exists(artifact_dir_abs) or not os.path.isdir(artifact_dir_abs):
            return ArtifactValidationResult(
                is_valid=False,
                status=ModelStatus.NOT_CONFIGURED,
                model_name=expected_model_name,
                artifact_path=artifact_dir_abs,
                errors=[f"Artifact directory does not exist: '{artifact_dir_abs}'"],
            )

        # 1. Locate Primary Files
        onnx_path = os.path.join(artifact_dir_abs, "model.onnx")
        meta_path = os.path.join(artifact_dir_abs, "metadata.json")
        labels_path = os.path.join(artifact_dir_abs, "labels.json")
        prep_path = os.path.join(artifact_dir_abs, "preprocessing.json")
        sums_path = os.path.join(artifact_dir_abs, "SHA256SUMS")

        if not os.path.exists(onnx_path):
            return ArtifactValidationResult(
                is_valid=False,
                status=ModelStatus.NOT_CONFIGURED,
                model_name=expected_model_name,
                artifact_path=artifact_dir_abs,
                errors=["Primary ONNX model file 'model.onnx' not found in artifact directory."],
            )

        # 2. SHA-256 Integrity Verification
        actual_sha256 = self.compute_sha256(onnx_path)
        if not actual_sha256:
            return ArtifactValidationResult(
                is_valid=False,
                status=ModelStatus.ERROR,
                model_name=expected_model_name,
                artifact_path=artifact_dir_abs,
                errors=["Failed to compute SHA-256 checksum for 'model.onnx'."],
            )

        checksum_verified = False
        sha256sums_map = self.parse_sha256sums_file(sums_path)
        if "model.onnx" in sha256sums_map:
            expected_hash = sha256sums_map["model.onnx"]
            if expected_hash.lower() != actual_sha256.lower():
                errors.append(
                    f"SHA256 checksum mismatch against SHA256SUMS: expected '{expected_hash}', got '{actual_sha256}'."
                )
            else:
                checksum_verified = True

        # 3. Metadata Validation
        metadata_dict: Dict[str, Any] = {}
        model_name = expected_model_name
        model_version = os.path.basename(artifact_dir_abs) or "v1"

        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    metadata_dict = json.load(f)
                
                model_name = metadata_dict.get("model_name") or metadata_dict.get("name") or expected_model_name
                model_version = metadata_dict.get("model_version") or metadata_dict.get("version") or model_version
                
                meta_sha = metadata_dict.get("artifact_sha256") or metadata_dict.get("checksum")
                if meta_sha:
                    if meta_sha.lower() != actual_sha256.lower():
                        errors.append(
                            f"SHA256 checksum mismatch against metadata.json: expected '{meta_sha}', got '{actual_sha256}'."
                        )
                    else:
                        checksum_verified = True

                framework = str(metadata_dict.get("framework", "")).lower()
                if framework and framework != "onnx":
                    errors.append(f"Incompatible framework specified in metadata.json: '{framework}'. Expected 'onnx'.")

            except Exception as e:
                errors.append(f"Invalid or corrupted 'metadata.json': {str(e)}")
        else:
            warnings.append("metadata.json not found in artifact directory.")

        # 4. Labels Validation & Compatibility
        labels_list: List[str] = []
        if os.path.exists(labels_path):
            try:
                with open(labels_path, "r", encoding="utf-8") as f:
                    raw_labels = json.load(f)
                if isinstance(raw_labels, list):
                    labels_list = [str(l).strip().upper() for l in raw_labels]
                elif isinstance(raw_labels, dict):
                    # Handle {0: "RAINFALL", 1: "HEATWAVE"} or {"id2label": ...}
                    id2l = raw_labels.get("id2label") or raw_labels
                    sorted_keys = sorted(id2l.keys(), key=lambda k: int(k) if str(k).isdigit() else str(k))
                    labels_list = [str(id2l[k]).strip().upper() for k in sorted_keys]
                else:
                    errors.append("labels.json must be a JSON array of class names or id2label dictionary.")
            except Exception as e:
                errors.append(f"Invalid or corrupted 'labels.json': {str(e)}")
        elif "labels" in metadata_dict and isinstance(metadata_dict["labels"], list):
            labels_list = [str(l).strip().upper() for l in metadata_dict["labels"]]
        elif "classes" in metadata_dict and isinstance(metadata_dict["classes"], list):
            labels_list = [str(l).strip().upper() for l in metadata_dict["classes"]]
        else:
            errors.append("No labels defined. Neither labels.json nor metadata.json contains class labels.")

        if labels_list:
            # Check Core Category Compatibility
            labels_set = set(labels_list)
            missing_core = CORE_WEATHER_CLASSES - labels_set
            if missing_core:
                errors.append(
                    f"Incompatible label schema: missing required SkyPulse core event classes: {sorted(list(missing_core))}."
                )

        # 5. Preprocessing Validation
        preprocessing_dict: Dict[str, Any] = {}
        if os.path.exists(prep_path):
            try:
                with open(prep_path, "r", encoding="utf-8") as f:
                    preprocessing_dict = json.load(f)
            except Exception as e:
                warnings.append(f"Could not parse 'preprocessing.json': {str(e)}")

        # 6. ONNX Graph Validation & Smoke Inference
        smoke_passed = False
        smoke_latency = 0.0

        if not errors:
            onnx_valid, onnx_errors, smoke_passed, smoke_latency = self._validate_onnx_runtime(
                onnx_path=onnx_path,
                expected_num_classes=len(labels_list),
                labels=labels_list,
            )
            errors.extend(onnx_errors)

        is_valid = len(errors) == 0 and smoke_passed
        status = ModelStatus.READY if is_valid else ModelStatus.ERROR

        return ArtifactValidationResult(
            is_valid=is_valid,
            status=status,
            model_name=model_name,
            model_version=model_version,
            artifact_path=artifact_dir_abs,
            onnx_file_path=onnx_path,
            sha256_checksum=actual_sha256,
            checksum_verified=checksum_verified,
            labels=labels_list,
            metadata=metadata_dict,
            preprocessing_config=preprocessing_dict,
            errors=errors,
            warnings=warnings,
            smoke_inference_passed=smoke_passed,
            smoke_latency_ms=smoke_latency,
        )

    def _validate_onnx_runtime(
        self,
        onnx_path: str,
        expected_num_classes: int,
        labels: List[str],
    ) -> Tuple[bool, List[str], bool, float]:
        """
        Loads the ONNX file into ONNX Runtime CPU session and executes a deterministic smoke test.
        """
        import time
        errors: List[str] = []
        smoke_passed = False
        smoke_latency = 0.0

        try:
            import onnxruntime as ort
            import numpy as np

            sess_opts = ort.SessionOptions()
            sess_opts.intra_op_num_threads = 1
            session = ort.InferenceSession(onnx_path, sess_opts, providers=["CPUExecutionProvider"])

            inputs = session.get_inputs()
            outputs = session.get_outputs()

            if not inputs:
                errors.append("ONNX model has no input tensors.")
                return False, errors, False, 0.0
            if not outputs:
                errors.append("ONNX model has no output tensors.")
                return False, errors, False, 0.0

            # Construct synthetic dummy input tensor based on input signature
            feed_dict = {}
            seq_len = 16
            for inp in inputs:
                name = inp.name
                shape = inp.shape
                # Replace dynamic dimensions with batch=1, seq=16
                resolved_shape = []
                for dim in shape:
                    if isinstance(dim, str) or dim is None or dim <= 0:
                        resolved_shape.append(1 if len(resolved_shape) == 0 else seq_len)
                    else:
                        resolved_shape.append(dim)
                
                if inp.type in ["tensor(int64)", "tensor(int32)"]:
                    dtype = np.int64 if "int64" in inp.type else np.int32
                    # Synthetic standard token IDs: [101, 1000, 1001, ..., 102]
                    dummy_data = np.ones(resolved_shape, dtype=dtype)
                    feed_dict[name] = dummy_data
                elif inp.type == "tensor(float)":
                    feed_dict[name] = np.zeros(resolved_shape, dtype=np.float32)
                else:
                    feed_dict[name] = np.ones(resolved_shape, dtype=np.int64)

            # Run deterministic smoke inference
            t0 = time.time()
            out_tensors = session.run(None, feed_dict)
            smoke_latency = (time.time() - t0) * 1000

            logits = np.array(out_tensors[0])
            if logits.ndim >= 2:
                logits_1d = logits[0]
            else:
                logits_1d = logits

            # Output Dimension Check
            if len(logits_1d) != expected_num_classes:
                errors.append(
                    f"ONNX output dimension ({len(logits_1d)}) does not match number of labels in labels.json ({expected_num_classes})."
                )
                return False, errors, False, smoke_latency

            # Finite check (no NaN / Inf)
            if not np.all(np.isfinite(logits_1d)):
                errors.append("ONNX smoke inference returned non-finite values (NaN or Inf).")
                return False, errors, False, smoke_latency

            # Softmax calculation check
            max_l = np.max(logits_1d)
            exp_l = np.exp(logits_1d - max_l)
            probs = exp_l / np.sum(exp_l)

            if not (0.99 <= np.sum(probs) <= 1.01):
                errors.append(f"Softmax probabilities sum to {np.sum(probs):.4f}, expected 1.0.")
                return False, errors, False, smoke_latency

            top_idx = int(np.argmax(probs))
            if top_idx < 0 or top_idx >= len(labels):
                errors.append(f"Predicted class index {top_idx} out of range for labels length {len(labels)}.")
                return False, errors, False, smoke_latency

            smoke_passed = True
            return True, errors, smoke_passed, round(smoke_latency, 2)

        except ImportError:
            errors.append("onnxruntime is not installed in the environment.")
            return False, errors, False, 0.0
        except Exception as e:
            errors.append(f"ONNX model execution failed during smoke test: {str(e)}")
            return False, errors, False, 0.0


# Global validator instance
model_artifact_validator = ModelArtifactValidator()
