"""
SkyPulse Multi-Level Deduplication Engine
Detects exact, near, and related weather reports across 4 gates:
- Level 1: Exact idempotency fingerprint match
- Level 2: Semantic embedding cosine similarity
- Level 3: Spatiotemporal window (<= 50km, <= 6 hours)
- Level 4: Media perceptual hash comparison

Outputs relationships: EXACT_DUPLICATE, NEAR_DUPLICATE, RELATED_REPORT, UNIQUE.
Never deletes duplicates; preserves evidence provenance and links to canonical events.
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field


class DuplicateEvaluation(BaseModel):
    verdict: str  # EXACT_DUPLICATE, NEAR_DUPLICATE, RELATED_REPORT, UNIQUE
    is_duplicate: bool
    similarity_score: float = Field(ge=0.0, le=1.0)
    matched_event_id: Optional[str] = None
    matched_report_id: Optional[str] = None
    level_matched: str  # IDEMPOTENCY_HASH, EMBEDDING_SEMANTIC, SPATIOTEMPORAL, MEDIA_PHASH, NONE
    spatial_distance_km: Optional[float] = None
    time_delta_hours: Optional[float] = None
    explanation: str


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two geographic coordinates in kilometers."""
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two unit or non-unit dense vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 < 1e-9 or norm2 < 1e-9:
        return 0.0
    return max(0.0, min(1.0, dot / (norm1 * norm2)))


class DeduplicationEngine:
    """
    Evaluates new reports against active canonical events or recent candidate reports.
    """

    DEDUP_TIME_WINDOW_HOURS = 6.0
    DEDUP_SPATIAL_RADIUS_KM = 50.0

    @classmethod
    def evaluate_candidate(
        cls,
        new_report: Dict[str, Any],
        candidate: Dict[str, Any],
    ) -> DuplicateEvaluation:
        """
        Evaluate candidate match across all 4 duplicate levels.
        """
        # --- Level 1: Exact Idempotency Fingerprint ---
        new_hash = new_report.get("idempotency_key")
        cand_hash = candidate.get("idempotency_key")
        if new_hash and cand_hash and new_hash == cand_hash:
            return DuplicateEvaluation(
                verdict="EXACT_DUPLICATE",
                is_duplicate=True,
                similarity_score=1.0,
                matched_report_id=str(candidate.get("id")),
                matched_event_id=str(candidate.get("canonical_event_id") or ""),
                level_matched="IDEMPOTENCY_HASH",
                explanation="Identical source content and external identifier hash match",
            )

        # --- Spatial & Temporal Calculations ---
        lat1, lon1 = new_report.get("latitude"), new_report.get("longitude")
        lat2, lon2 = candidate.get("latitude"), candidate.get("longitude")

        distance_km = None
        if lat1 is not None and lon1 is not None and lat2 is not None and lon2 is not None:
            distance_km = haversine_distance_km(lat1, lon1, lat2, lon2)

        # Time delta
        t1 = new_report.get("event_time") or datetime.now(timezone.utc)
        t2 = candidate.get("event_time") or datetime.now(timezone.utc)
        if isinstance(t1, str):
            t1 = datetime.fromisoformat(t1.replace("Z", "+00:00"))
        if isinstance(t2, str):
            t2 = datetime.fromisoformat(t2.replace("Z", "+00:00"))
        if getattr(t1, "tzinfo", None) is None:
            t1 = t1.replace(tzinfo=timezone.utc)
        if getattr(t2, "tzinfo", None) is None:
            t2 = t2.replace(tzinfo=timezone.utc)

        time_delta_h = abs((t1 - t2).total_seconds()) / 3600.0

        # Category match
        cat1 = (new_report.get("primary_category") or "").upper()
        cat2 = (candidate.get("primary_category") or candidate.get("category") or "").upper()
        if cat1 and cat2 and cat1 == cat2:
            category_match = 1.0
        elif (cat1, cat2) in [("FLOODING", "RAINFALL"), ("RAINFALL", "FLOODING"), ("THUNDERSTORM", "RAINFALL"), ("RAINFALL", "THUNDERSTORM")]:
            category_match = 0.85
        else:
            category_match = 0.0

        # --- Level 4: Media pHash match ---
        new_phash = new_report.get("phash")
        cand_phash = candidate.get("phash")
        media_score = 0.0
        if new_phash and cand_phash:
            # Hamming distance on 16-hex char hash
            mismatches = sum(c1 != c2 for c1, c2 in zip(new_phash, cand_phash))
            media_score = max(0.0, 1.0 - (mismatches / 16.0))

        # --- Level 2: Semantic embedding similarity ---
        emb1 = new_report.get("embedding")
        emb2 = candidate.get("embedding")
        semantic_sim = 0.0
        if emb1 and emb2:
            semantic_sim = cosine_similarity(emb1, emb2)
        else:
            # Fallback text token overlap
            t_txt1 = set(str(new_report.get("text", "")).lower().split())
            t_txt2 = set(str(candidate.get("text", "")).lower().split())
            if t_txt1 and t_txt2:
                intersect = len(t_txt1 & t_txt2)
                union = len(t_txt1 | t_txt2)
                semantic_sim = intersect / union if union > 0 else 0.0

        # --- Level 3: Spatiotemporal proximity gate ---
        is_spatially_close = (distance_km is not None and distance_km <= cls.DEDUP_SPATIAL_RADIUS_KM)
        is_temporally_close = (time_delta_h <= cls.DEDUP_TIME_WINDOW_HOURS)

        # Spatial score: 1.0 at 0km, down to 0.0 at 50km
        spatial_score = 0.0
        if distance_km is not None:
            spatial_score = max(0.0, 1.0 - (distance_km / cls.DEDUP_SPATIAL_RADIUS_KM))

        # Composite score
        # 0.40 * semantic + 0.25 * category + 0.20 * spatial + 0.15 * media
        composite_score = (
            0.40 * semantic_sim
            + 0.25 * category_match
            + 0.20 * spatial_score
            + 0.15 * (media_score if media_score > 0 else semantic_sim)
        )

        # Verdict logic
        if media_score >= 0.90 and is_temporally_close:
            return DuplicateEvaluation(
                verdict="EXACT_DUPLICATE",
                is_duplicate=True,
                similarity_score=round(composite_score, 2),
                matched_report_id=str(candidate.get("id")),
                matched_event_id=str(candidate.get("canonical_event_id") or ""),
                level_matched="MEDIA_PHASH",
                spatial_distance_km=round(distance_km, 2) if distance_km is not None else None,
                time_delta_hours=round(time_delta_h, 2),
                explanation="Matching media perceptual hash within active observation window",
            )

        if is_spatially_close and is_temporally_close and category_match >= 0.80:
            if composite_score >= 0.65 or (spatial_score >= 0.85 and time_delta_h <= 2.0):
                return DuplicateEvaluation(
                    verdict="NEAR_DUPLICATE",
                    is_duplicate=True,
                    similarity_score=round(composite_score, 2),
                    matched_report_id=str(candidate.get("id")),
                    matched_event_id=str(candidate.get("canonical_event_id") or ""),
                    level_matched="SPATIOTEMPORAL",
                    spatial_distance_km=round(distance_km, 2) if distance_km is not None else None,
                    time_delta_hours=round(time_delta_h, 2),
                    explanation=f"Corroborating observation within {distance_km:.1f}km and {time_delta_h:.1f}h",
                )
            elif composite_score >= 0.35:
                return DuplicateEvaluation(
                    verdict="RELATED_REPORT",
                    is_duplicate=False,
                    similarity_score=round(composite_score, 2),
                    matched_report_id=str(candidate.get("id")),
                    matched_event_id=str(candidate.get("canonical_event_id") or ""),
                    level_matched="SPATIOTEMPORAL",
                    spatial_distance_km=round(distance_km, 2) if distance_km is not None else None,
                    time_delta_hours=round(time_delta_h, 2),
                    explanation="Related meteorological event in neighboring vicinity",
                )

        return DuplicateEvaluation(
            verdict="UNIQUE",
            is_duplicate=False,
            similarity_score=round(composite_score, 2),
            matched_report_id=None,
            matched_event_id=None,
            level_matched="NONE",
            spatial_distance_km=round(distance_km, 2) if distance_km is not None else None,
            time_delta_hours=round(time_delta_h, 2),
            explanation="Distinct geographic or meteorological observation",
        )
