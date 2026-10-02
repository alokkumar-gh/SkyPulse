"""
SkyPulse Dataset Training Readiness Evaluation Engine.
======================================================
Deterministically evaluates whether an assembled dataset is ready for supervised ML training.
Audits sample volume, class coverage, severe imbalance, language distribution, and leakage risks.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from collections import Counter

from ml.schemas import (
    TrainingRecord,
    DatasetReadiness,
    DatasetReadinessReport,
    WeatherEventCategory,
)

logger = logging.getLogger("skypulse.ml.readiness")

MIN_SAMPLES_PER_CLASS_RECOMMENDED = 100
MIN_TOTAL_SAMPLES_RECOMMENDED = 1000
CORE_CANONICAL_CLASSES = [
    WeatherEventCategory.RAINFALL.value,
    WeatherEventCategory.THUNDERSTORM.value,
    WeatherEventCategory.FLOODING.value,
    WeatherEventCategory.HEATWAVE.value,
    WeatherEventCategory.FOG.value,
    WeatherEventCategory.DUST_STORM.value,
    WeatherEventCategory.STRONG_WINDS.value,
]


class ReadinessEngine:
    """
    Evaluates dataset quality and sufficiency for training without inventing metrics.
    """

    def evaluate_readiness(
        self,
        records: List[TrainingRecord],
        split_meta: Optional[Dict[str, Any]] = None,
    ) -> DatasetReadinessReport:
        """
        Runs comprehensive checks and generates an auditable DatasetReadinessReport.
        """
        now_str = datetime.now(timezone.utc).isoformat()
        if not records:
            return DatasetReadinessReport(
                status=DatasetReadiness.NOT_READY,
                overall_score=0.0,
                total_samples=0,
                warnings=["Dataset is completely empty."],
                blockers=["No training records found."],
                evaluated_at=now_str,
            )

        total_n = len(records)
        class_counts = Counter(r.category.value for r in records)
        lang_counts = Counter(r.language for r in records)

        warnings: List[str] = []
        blockers: List[str] = []

        # 1. Total volume evaluation
        if total_n < 50:
            blockers.append(f"Insufficient total samples: {total_n} (minimum required: 50).")
        elif total_n < MIN_TOTAL_SAMPLES_RECOMMENDED:
            warnings.append(f"Dataset size ({total_n}) is below recommended production volume ({MIN_TOTAL_SAMPLES_RECOMMENDED}).")

        # 2. Per-class representation evaluation
        insufficient_classes: List[str] = []
        missing_classes: List[str] = []
        for cat in CORE_CANONICAL_CLASSES:
            count = class_counts.get(cat, 0)
            if count == 0:
                missing_classes.append(cat)
            elif count < 10:
                insufficient_classes.append(f"{cat} (count={count})")
            elif count < MIN_SAMPLES_PER_CLASS_RECOMMENDED:
                warnings.append(f"Class '{cat}' has low sample count ({count} < {MIN_SAMPLES_PER_CLASS_RECOMMENDED}).")

        if missing_classes:
            warnings.append(f"Missing core weather event classes: {', '.join(missing_classes)}.")

        # 3. Class imbalance check
        valid_counts = [cnt for cat, cnt in class_counts.items() if cat != "UNKNOWN" and cnt > 0]
        if valid_counts:
            max_c = max(valid_counts)
            min_c = min(valid_counts)
            ratio = max_c / max(1, min_c)
            if ratio > 20.0:
                warnings.append(f"High class imbalance detected (ratio={ratio:.1f}:1). Class weighting recommended.")

        # 4. Leakage audit
        temporal_leakage = False
        spatial_leakage = False
        if split_meta:
            temporal_leakage = bool(split_meta.get("temporal_leakage_detected"))
            spatial_leakage = bool(split_meta.get("spatial_event_leakage_detected"))
            if temporal_leakage:
                blockers.append("Temporal data leakage detected across train/val/test splits.")
            if spatial_leakage:
                warnings.append("Spatial or event cluster overlap detected across splits.")

        # 5. Language diversity check
        if lang_counts.get("hi", 0) == 0:
            warnings.append("No Devanagari Hindi records in dataset. English-dominant classification only.")

        # Compute status and readiness score
        score = min(1.0, total_n / 5000.0) * 0.4
        score += (len(class_counts) / len(CORE_CANONICAL_CLASSES)) * 0.3
        score += 0.3 if not blockers else 0.0
        score = round(max(0.0, min(1.0, score)), 2)

        if blockers:
            status = DatasetReadiness.NOT_READY
        elif warnings:
            status = DatasetReadiness.READY_WITH_WARNINGS
        else:
            status = DatasetReadiness.READY

        return DatasetReadinessReport(
            status=status,
            overall_score=score,
            total_samples=total_n,
            class_counts=dict(class_counts),
            insufficient_classes=insufficient_classes,
            warnings=warnings,
            blockers=blockers,
            temporal_leakage_detected=temporal_leakage,
            spatial_leakage_detected=spatial_leakage,
            evaluated_at=now_str,
        )


readiness_engine = ReadinessEngine()
