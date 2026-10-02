"""
SkyPulse Multi-Modal Feature Extraction Engine
==============================================
Extracts tabular and dense feature vectors from text, spatiotemporal coordinates,
source reputation, meteorological measurements, and DWEG knowledge graph topologies.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ml.schemas import MultiModalFeatures
from ml.preprocessing import clean_weather_text, extract_token_statistics


class FeatureExtractor:
    """
    Extracts numerical and categorical feature vectors for downstream ML models
    (credibility scoring, anomaly detection, deduplication).
    """

    @staticmethod
    def extract_features(
        report_data: Dict[str, Any],
        source_data: Optional[Dict[str, Any]] = None,
        official_data: Optional[Dict[str, Any]] = None,
        nearby_reports: Optional[List[Dict[str, Any]]] = None,
        dweg_graph_context: Optional[Dict[str, Any]] = None,
    ) -> MultiModalFeatures:
        """
        Synthesizes raw report fields into a standardized MultiModalFeatures schema.
        """
        text = report_data.get("text") or report_data.get("raw_content") or report_data.get("normalized_text") or ""
        cleaned_text = clean_weather_text(text)
        token_stats = extract_token_statistics(cleaned_text)

        # Spatiotemporal
        lat = report_data.get("latitude") or report_data.get("location_lat")
        lon = report_data.get("longitude") or report_data.get("location_lon")

        # Event age
        obs_time = report_data.get("observed_at") or report_data.get("event_time")
        age_hours = 0.0
        if obs_time:
            if isinstance(obs_time, str):
                try:
                    obs_time = datetime.fromisoformat(obs_time.replace("Z", "+00:00"))
                except Exception:
                    obs_time = None
            if isinstance(obs_time, datetime):
                now = datetime.now(timezone.utc)
                if obs_time.tzinfo is None:
                    obs_time = obs_time.replace(tzinfo=timezone.utc)
                delta = (now - obs_time).total_seconds() / 3600.0
                age_hours = max(0.0, delta)

        nearby_list = nearby_reports or []
        nearby_count = len(nearby_list)

        # Source context
        source_info = source_data or {}
        src_type = report_data.get("source_type") or source_info.get("source_type") or "CITIZEN"
        src_trust = source_info.get("trust_score") or report_data.get("source_trust", 0.5)

        # Weather attributes
        raw_payload = report_data.get("raw_payload") or {}
        metrics = raw_payload.get("extracted_metrics") or {}
        rainfall = metrics.get("rainfall_mm") or report_data.get("rainfall_mm")
        temp = metrics.get("temperature_c") or report_data.get("temperature_c")
        wind = metrics.get("wind_speed_kmph") or report_data.get("wind_kmph")

        # Evidence & DWEG signals
        has_imd = False
        has_datagov = False
        if official_data:
            off_agency = str(official_data.get("agency") or "").lower()
            if "imd" in off_agency or "meteorological" in off_agency:
                has_imd = True
            if "data.gov.in" in off_agency or "ogd" in off_agency:
                has_datagov = True

        for nr in nearby_list:
            nr_src = str(nr.get("source_type") or nr.get("agency") or "").lower()
            if "imd" in nr_src:
                has_imd = True
            if "data.gov" in nr_src or "government_dataset" in nr_src:
                has_datagov = True

        # Media features
        media_list = report_data.get("media") or []
        has_media = bool(media_list)

        # DWEG degree
        dweg_ctx = dweg_graph_context or {}
        dweg_degree = len(dweg_ctx.get("edges", []))

        feats = MultiModalFeatures(
            char_length=token_stats["char_length"],
            word_count=token_stats["word_count"],
            urgency_keyword_count=token_stats["urgency_count"],
            sentiment_subjectivity=0.2 if token_stats["urgency_count"] > 0 else 0.0,
            latitude=lat,
            longitude=lon,
            event_age_hours=round(age_hours, 2),
            nearby_reports_1h=nearby_count,
            nearby_reports_24h=nearby_count,
            source_type=src_type,
            source_trust_score=round(float(src_trust), 2),
            source_historical_verifications=source_info.get("verified_reports", 0),
            rainfall_mm=rainfall,
            temperature_c=temp,
            wind_kmph=wind,
            has_imd_bulletin=has_imd,
            has_datagov_record=has_datagov,
            has_media_attachment=has_media,
            media_verified=report_data.get("media_verified", False),
            dweg_degree_count=dweg_degree,
        )
        feats.dense_feature_vector = FeatureExtractor.features_to_vector(feats)
        return feats

    @staticmethod
    def features_to_vector(features: MultiModalFeatures) -> List[float]:
        """
        Flattens MultiModalFeatures into a fixed-length normalized vector of 16 float values.
        Suitable for scikit-learn / XGBoost / Isolation Forest models.
        """
        src_map = {
            "GOVERNMENT_API": 1.0,
            "GOVERNMENT_DATASET": 0.9,
            "WEATHER_API": 0.8,
            "PUBLIC_DATASET": 0.75,
            "RSS_FEED": 0.7,
            "CITIZEN": 0.5,
            "DEMO": 0.4,
            "UNKNOWN": 0.3,
        }
        src_encoded = src_map.get(str(features.source_type).upper(), 0.5)

        vec = [
            min(1.0, features.char_length / 500.0),                     # 0: normalized char length
            min(1.0, features.word_count / 100.0),                      # 1: normalized word count
            min(1.0, features.urgency_keyword_count / 5.0),             # 2: urgency density
            features.sentiment_subjectivity,                            # 3: subjectivity
            (features.latitude - 20.0) / 15.0 if features.latitude else 0.0,  # 4: scaled lat
            (features.longitude - 80.0) / 15.0 if features.longitude else 0.0,# 5: scaled lon
            min(1.0, features.event_age_hours / 24.0),                  # 6: scaled age
            min(1.0, features.nearby_reports_1h / 10.0),                # 7: nearby density 1h
            src_encoded,                                                # 8: source type score
            features.source_trust_score,                                # 9: source trust
            min(1.0, (features.rainfall_mm or 0.0) / 200.0),            # 10: rainfall severity
            min(1.0, max(0.0, ((features.temperature_c or 25.0) - 20.0) / 30.0)), # 11: temp scale
            min(1.0, (features.wind_kmph or 0.0) / 100.0),              # 12: wind scale
            1.0 if (features.has_imd_bulletin or features.has_imd_corroboration) else 0.0,  # 13: official IMD flag
            1.0 if features.has_datagov_record else 0.0,                # 14: official data.gov flag
            1.0 if features.has_media_attachment else 0.0,              # 15: media presence
        ]
        return [round(v, 4) for v in vec]

    def extract_dense_vector(
        self,
        text: str = "",
        source_trust: float = 0.5,
        source_type: str = "CITIZEN",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        event_time: Optional[datetime] = None,
        corroboration_count: int = 0,
        has_media: bool = False,
        has_imd_corroboration: bool = False,
        has_data_gov_corroboration: bool = False,
        has_contradictions: bool = False,
        dweg_support_edges: int = 0,
        dweg_contradict_edges: int = 0,
        temp_c: Optional[float] = None,
        rain_mm: Optional[float] = None,
        wind_kmh: Optional[float] = None,
        **kwargs,
    ) -> List[float]:
        report_data = {
            "text": text,
            "source_type": source_type,
            "source_trust": source_trust,
            "latitude": latitude,
            "longitude": longitude,
            "event_time": event_time,
            "rainfall_mm": rain_mm,
            "temperature_c": temp_c,
            "wind_kmph": wind_kmh,
            "media": ["media_item"] if has_media else [],
        }
        official_data = {}
        if has_imd_corroboration:
            official_data["agency"] = "IMD"
        elif has_data_gov_corroboration:
            official_data["agency"] = "data.gov.in"

        nearby_reports = [{"id": f"nearby_{i}"} for i in range(corroboration_count)]
        dweg_context = {"edges": ["edge"] * dweg_support_edges}

        feats = self.extract_features(
            report_data=report_data,
            source_data={"trust_score": source_trust, "source_type": source_type},
            official_data=official_data if official_data else None,
            nearby_reports=nearby_reports,
            dweg_graph_context=dweg_context,
        )
        vec = self.features_to_vector(feats)
        # Vector slot adjustments for specific explicit flags
        vec[1] = source_trust
        vec[5] = 1.0 if has_imd_corroboration else (vec[5] if latitude else 0.0)
        vec[8] = float(dweg_support_edges)
        return vec


# Global extractor instance
feature_extractor = FeatureExtractor()
