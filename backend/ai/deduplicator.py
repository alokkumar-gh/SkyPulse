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
    DEDUP_SPATIAL_RADIUS_KM = 25.0

    @classmethod
    def evaluate_candidate(
        cls,
        new_report: Dict[str, Any],
        candidate: Dict[str, Any],
    ) -> DuplicateEvaluation:
        """
        Evaluate candidate match across all 4 duplicate levels.
        Enforces strict meteorological distinction:
        - Never merges different hazard categories (e.g. RAINFALL vs HEATWAVE vs DUST_STORM)
        - Never merges distant locations (> 25 km or distinct cities/taluks)
        - Never merges observations outside the 6-hour active weather window
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

        # Administrative location matching
        st1 = (new_report.get("state") or new_report.get("location_state") or "").lower().strip()
        st2 = (candidate.get("state") or candidate.get("primary_state") or candidate.get("location_state") or "").lower().strip()
        dist1 = (new_report.get("district") or new_report.get("location_district") or "").lower().strip()
        dist2 = (candidate.get("district") or candidate.get("primary_district") or "").lower().strip()
        city1 = (new_report.get("city") or new_report.get("location_city") or "").lower().strip()
        city2 = (candidate.get("city") or candidate.get("primary_city") or "").lower().strip()

        admin_match = 0.0
        if st1 and st2 and (st1 == st2 or st1 in st2 or st2 in st1):
            if city1 and city2:
                c1_clean = city1.replace("bengaluru", "bangalore").replace("bhubaneswar", "bhubaneshwar")
                c2_clean = city2.replace("bengaluru", "bangalore").replace("bhubaneswar", "bhubaneshwar")
                if c1_clean == c2_clean or c1_clean in c2_clean or c2_clean in c1_clean:
                    admin_match = 1.0
                else:
                    admin_match = 0.0  # Different distinct cities in same state CANNOT be merged (Section 15)
            elif dist1 and dist2:
                d1_clean = dist1.replace("khordha", "khurda").replace("bengaluru", "bangalore")
                d2_clean = dist2.replace("khordha", "khurda").replace("bengaluru", "bangalore")
                if d1_clean == d2_clean or d1_clean in d2_clean or d2_clean in d1_clean:
                    admin_match = 1.0
                else:
                    admin_match = 0.0  # Different distinct districts in same state CANNOT be merged (Section 15)
            elif (city1 or dist1) and (not city2 and not dist2):
                # Specific district/city report should NOT collapse into general state-level candidate
                admin_match = 0.15
            elif (city2 or dist2) and (not city1 and not dist1):
                # General state-level report should NOT collapse into specific district candidate
                admin_match = 0.15
            elif not dist1 and not dist2 and not city1 and not city2:
                # Both are broad state-level regional reports in the same state
                admin_match = 0.70
            else:
                admin_match = 0.0

        # Category match - strict distinction
        cat1 = (new_report.get("primary_category") or new_report.get("category") or "").upper()
        cat2 = (candidate.get("primary_category") or candidate.get("category") or "").upper()
        if cat1 and cat2 and cat1 == cat2:
            category_match = 1.0
        elif (cat1, cat2) in [
            ("FLOODING", "RAINFALL"), ("RAINFALL", "FLOODING"),
        ]:
            # Direct causal compound relationship
            category_match = 0.80
        elif cat1 == "UNKNOWN" or cat2 == "UNKNOWN":
            category_match = 0.50
        else:
            category_match = 0.0

        # If categories are incompatible, they CANNOT be merged
        if category_match < 0.50:
            return DuplicateEvaluation(
                verdict="UNIQUE",
                is_duplicate=False,
                similarity_score=0.0,
                matched_report_id=None,
                matched_event_id=None,
                level_matched="NONE",
                spatial_distance_km=round(distance_km, 2) if distance_km is not None else None,
                time_delta_hours=round(time_delta_h, 2),
                explanation=f"Distinct weather hazard phenomena ({cat1} vs {cat2})",
            )

        # Incompatible semantic subtypes (e.g. RAINFALL_DEFICIT vs active RAINFALL_OBSERVED/HEAVY_RAINFALL)
        sub1 = (new_report.get("sub_category") or new_report.get("phenomenon") or "").upper()
        sub2 = (candidate.get("sub_category") or candidate.get("phenomenon") or "").upper()
        if (sub1 == "RAINFALL_DEFICIT" and sub2 in ("RAINFALL_OBSERVED", "HEAVY_RAINFALL", "EXTREME_RAINFALL", "CLOUDBURST")) or \
           (sub2 == "RAINFALL_DEFICIT" and sub1 in ("RAINFALL_OBSERVED", "HEAVY_RAINFALL", "EXTREME_RAINFALL", "CLOUDBURST")):
            return DuplicateEvaluation(
                verdict="UNIQUE",
                is_duplicate=False,
                similarity_score=0.0,
                matched_report_id=None,
                matched_event_id=None,
                level_matched="NONE",
                spatial_distance_km=round(distance_km, 2) if distance_km is not None else None,
                time_delta_hours=round(time_delta_h, 2),
                explanation=f"Incompatible meteorological phenomena (Seasonal {sub1 or 'DEFICIT'} vs Observed {sub2 or 'RAINFALL'})",
            )

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
        is_spatially_close = False
        spatial_score = 0.0
        if distance_km is not None:
            is_spatially_close = (distance_km <= cls.DEDUP_SPATIAL_RADIUS_KM)
            spatial_score = max(0.0, 1.0 - (distance_km / cls.DEDUP_SPATIAL_RADIUS_KM))
        elif admin_match >= 0.80:
            is_spatially_close = True
            spatial_score = admin_match

        is_temporally_close = (time_delta_h <= cls.DEDUP_TIME_WINDOW_HOURS)

        # Composite score
        composite_score = (
            0.35 * semantic_sim
            + 0.30 * category_match
            + 0.25 * spatial_score
            + 0.10 * (media_score if media_score > 0 else semantic_sim)
        )

        # Verdict logic
        if media_score >= 0.90 and is_temporally_close:
            return DuplicateEvaluation(
                verdict="EXACT_DUPLICATE",
                is_duplicate=True,
                similarity_score=round(composite_score, 2),
                matched_report_id=str(candidate.get("id")),
                matched_event_id=str(candidate.get("canonical_event_id") or candidate.get("id") or ""),
                level_matched="MEDIA_PHASH",
                spatial_distance_km=round(distance_km, 2) if distance_km is not None else None,
                time_delta_hours=round(time_delta_h, 2),
                explanation="Matching media perceptual hash within active observation window",
            )

        if is_spatially_close and is_temporally_close and category_match >= 0.70:
            # Require minimum content similarity so distinct stories in same area remain distinct (Section 15)
            if composite_score >= 0.65 and semantic_sim >= 0.40:
                return DuplicateEvaluation(
                    verdict="NEAR_DUPLICATE",
                    is_duplicate=True,
                    similarity_score=round(composite_score, 2),
                    matched_report_id=str(candidate.get("id")),
                    matched_event_id=str(candidate.get("canonical_event_id") or candidate.get("id") or ""),
                    level_matched="SPATIOTEMPORAL",
                    spatial_distance_km=round(distance_km, 2) if distance_km is not None else None,
                    time_delta_hours=round(time_delta_h, 2),
                    explanation=f"Corroborating observation within {'%.1fkm' % distance_km if distance_km is not None else 'same district/state'} and {time_delta_h:.1f}h",
                )
            elif composite_score >= 0.35:
                return DuplicateEvaluation(
                    verdict="RELATED_REPORT",
                    is_duplicate=False,
                    similarity_score=round(composite_score, 2),
                    matched_report_id=str(candidate.get("id")),
                    matched_event_id=str(candidate.get("canonical_event_id") or candidate.get("id") or ""),
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
