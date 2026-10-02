"""
SkyPulse Semantic Deduplication ML Model
========================================
Combines dense sentence embeddings, cosine similarity, and spatiotemporal
distance metrics to distinguish exact duplicates, near-duplicates, and related events.
"""

import math
import hashlib
from typing import List, Optional, Tuple

from ml.schemas import MLDuplicateMatch
from ml.model_registry import model_registry
from ml.model_loader import model_loader
from ml.preprocessing import clean_weather_text
from app.core.config import settings


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two GPS coordinates in kilometers."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Computes cosine similarity between two dense embedding vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm1 * norm2)))


def generate_fallback_embedding(text: str, dim: int = 384) -> List[float]:
    """
    Generates a deterministic 384-dimensional dense pseudo-embedding via feature hashing
    (token-level + char 3-gram hashing trick) when an ML embedding model is not yet loaded on disk.
    Preserves semantic and lexical overlap for cosine similarity search.
    """
    cleaned = clean_weather_text(text).lower()
    tokens = cleaned.split()
    features = list(tokens)
    for token in tokens:
        if len(token) >= 3:
            for j in range(len(token) - 2):
                features.append(token[j : j + 3])

    vec = [0.0] * dim
    if not features:
        return vec

    for feat in features:
        h = int(hashlib.sha256(feat.encode("utf-8")).hexdigest()[:8], 16)
        idx = h % dim
        sign = 1.0 if (h & 0x100) else -1.0
        vec[idx] += sign

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [round(x / norm, 5) for x in vec]
    return vec


class SemanticDuplicateModel:
    """
    Embeds text and evaluates semantic and geospatial similarity to detect duplicates.
    """

    def __init__(self, model_name: str = "sentence_embedding_model"):
        self.model_name = model_name
        self.sim_threshold = float(getattr(settings, "ML_DUPLICATE_THRESHOLD", 0.85) or 0.85)

    def encode(self, text: str) -> List[float]:
        """
        Generates a 384-dimensional dense semantic embedding vector.
        Uses loaded HuggingFace model if available, else deterministic fallback vector.
        """
        model = model_loader.load_model(self.model_name)
        if model is not None and hasattr(model, "encode"):
            try:
                emb = model.encode(text, normalize_embeddings=True)
                return [round(float(x), 5) for x in emb]
            except Exception:
                pass
        return generate_fallback_embedding(text, dim=384)

    def evaluate_pair(
        self,
        text1: str,
        text2: str,
        lat1: Optional[float] = None,
        lon1: Optional[float] = None,
        lat2: Optional[float] = None,
        lon2: Optional[float] = None,
        time_delta_seconds: Optional[float] = None,
    ) -> MLDuplicateMatch:
        """
        Assesses whether two reports are EXACT_DUPLICATE, NEAR_DUPLICATE, RELATED_REPORT, or UNIQUE.
        """
        emb1 = self.encode(text1)
        emb2 = self.encode(text2)
        sim = cosine_similarity(emb1, emb2)

        dist_km: Optional[float] = None
        if lat1 is not None and lon1 is not None and lat2 is not None and lon2 is not None:
            dist_km = haversine_distance_km(lat1, lon1, lat2, lon2)

        delta_sec = abs(time_delta_seconds) if time_delta_seconds is not None else 0.0

        # Classification decision rules
        if sim >= 0.98 and (dist_km is None or dist_km < 1.0) and delta_sec < 1800:
            match_type = "EXACT_DUPLICATE"
        elif sim >= self.sim_threshold and (dist_km is None or dist_km < 5.0) and delta_sec < 7200:
            match_type = "NEAR_DUPLICATE"
        elif sim >= 0.65 and (dist_km is None or dist_km < 25.0) and delta_sec < 21600:
            match_type = "RELATED_REPORT"
        else:
            match_type = "UNIQUE"

        return MLDuplicateMatch(
            match_type=match_type,
            similarity_score=round(sim, 3),
            spatial_distance_km=round(dist_km, 2) if dist_km is not None else None,
            temporal_delta_seconds=round(delta_sec, 1) if time_delta_seconds is not None else None,
        )

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        return cosine_similarity(vec1, vec2)

    async def evaluate_duplicate_candidate(
        self,
        report_text: str,
        candidate_text: str,
        report_lat: Optional[float] = None,
        report_lon: Optional[float] = None,
        candidate_lat: Optional[float] = None,
        candidate_lon: Optional[float] = None,
        time_delta_seconds: Optional[float] = None,
    ) -> MLDuplicateMatch:
        return self.evaluate_pair(
            text1=report_text,
            text2=candidate_text,
            lat1=report_lat,
            lon1=report_lon,
            lat2=candidate_lat,
            lon2=candidate_lon,
            time_delta_seconds=time_delta_seconds,
        )


# Global duplicate model instance
duplicate_model = SemanticDuplicateModel()
