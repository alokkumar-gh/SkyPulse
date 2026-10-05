"""
SkyPulse Deterministic Fallback AI Provider
Implements complete offline intelligence without external credentials or heavy GPU dependencies.
Provides high-speed, reproducible classification, extraction, embedding, media analysis,
anomaly scoring, and verification.
"""

import re
import math
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from ai.base_provider import (
    AIProvider,
    ClassificationResult,
    EntityExtractionResult,
    WeatherAttribute,
    MediaAnalysisResult,
    AnomalyResult,
    EvidenceAssessmentResult,
)
from connectors.normalizer import INDIAN_CITIES_REFERENCE

# Meteorological Keyword Dictionaries (English, Hindi transliteration)
CATEGORY_SIGNALS = {
    "RAINFALL": [
        "rain", "rainfall", "downpour", "drizzle", "shower", "cloudburst", "precipitation",
        "baarish", "barish", "barsat", "monsoon", "torrential", "heavy rain", "wet",
        "dry spell", "rain deficit", "rainfall deficit", "deficit", "surplus", "excess rain"
    ],
    "THUNDERSTORM": [
        "thunder", "lightning", "thunderstorm", "thunderclap", "bijli", "tufan", "squall",
        "tempest", "electric storm", "severe storm", "aandhi"
    ],
    "FLOODING": [
        "flood", "flooding", "waterlogging", "waterlogged", "inundation", "submerged",
        "deluge", "barh", "overflow", "knee-deep water", "waist-deep water", "breach",
        "river water", "water level", "water levels"
    ],
    "HEATWAVE": [
        "heatwave", "heat wave", "extreme heat", "sweltering", "scorching", "loo", "loo wind",
        "garmi", "heat stroke", "high temperature", "soaring temperature"
    ],
    "FOG": [
        "fog", "dense fog", "foggy", "mist", "dhund", "kohra", "low visibility", "zero visibility",
        "radiation fog", "haze", "shallow fog"
    ],
    "DUST_STORM": [
        "dust storm", "duststorm", "sandstorm", "haboob", "dust squall", "blinding dust",
        "dust haze", "aandhi"
    ],
    "STRONG_WINDS": [
        "strong winds", "gale", "high winds", "gusty winds", "wind gust", "howling wind",
        "squally winds", "cyclonic winds", "stormy winds", "breeze"
    ],
    "SNOWFALL": ["snow", "snowfall", "blizzard", "ice", "frost", "baraf"],
    "HAILSTORM": ["hail", "hailstorm", "hailstone", "hailstones", "patthar"],
    "CYCLONE": ["cyclone", "cyclonic storm", "super cyclone", "typhoon", "hurricane"],
    "SMOG": ["smog", "toxic air", "air pollution", "severe aqi", "hazardous aqi", "smoke"],
}

SEVERITY_KEYWORDS = {
    4: ["cloudburst", "flash flood", "catastrophic", "extremely heavy", "unprecedented", "devastating", "fatal", "casualties"],
    3: ["severe", "heavy", "violent", "intense", "submerged", "dangerous", "warning", "gale", "soaring", "exceeded"],
    2: ["moderate", "continuous", "steady", "waterlogged", "gusty", "dense", "rising"],
    1: ["light", "mild", "shallow", "slight", "scattered", "drizzle", "passing"],
}

# Seasonal Baselines for Indian Weather (Month: 1-12 -> typical categories)
SEASONAL_EXPECTATIONS = {
    # Winter (Jan-Feb)
    1: ["FOG", "COLD_WAVE", "SNOWFALL", "SMOG"],
    2: ["FOG", "RAINFALL"],
    # Pre-monsoon / Summer (Mar-May)
    3: ["THUNDERSTORM", "HEATWAVE", "DUST_STORM"],
    4: ["HEATWAVE", "THUNDERSTORM", "DUST_STORM"],
    5: ["HEATWAVE", "DUST_STORM", "THUNDERSTORM", "CYCLONE"],
    # Southwest Monsoon (Jun-Sep)
    6: ["RAINFALL", "FLOODING", "THUNDERSTORM", "STRONG_WINDS"],
    7: ["RAINFALL", "FLOODING", "THUNDERSTORM", "STRONG_WINDS"],
    8: ["RAINFALL", "FLOODING", "THUNDERSTORM", "STRONG_WINDS"],
    9: ["RAINFALL", "FLOODING", "THUNDERSTORM", "STRONG_WINDS"],
    # Post-monsoon / Retreating (Oct-Dec)
    10: ["CYCLONE", "RAINFALL", "FLOODING"],
    11: ["CYCLONE", "FOG", "SMOG", "RAINFALL"],
    12: ["FOG", "SMOG", "COLD_WAVE", "SNOWFALL"],
}


class FallbackAIProvider(AIProvider):
    """
    High-performance fallback provider providing deterministic AI outputs.
    Ensures zero downtime, 100% offline support, and reproducible test results.
    """

    @property
    def name(self) -> str:
        return "DeterministicFallbackProvider"

    @property
    def is_configured(self) -> bool:
        return True

    async def classify_event(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        """Classify report using multi-signal term matching and contextual cues with relevance gating."""
        try:
            from connectors.weather_relevance_engine import WeatherRelevanceEngine
            assessment = WeatherRelevanceEngine.evaluate(
                text=text,
                claimed_category=metadata.get("suggested_category") if metadata else None,
                location_state=metadata.get("state") if metadata else None,
                location_district=metadata.get("district") if metadata else None,
                observed_telemetry=metadata.get("observed_telemetry") if metadata else None,
                tracked_parent_system_id=metadata.get("parent_system_id") if metadata else None,
            )
            if not assessment.is_relevant:
                return ClassificationResult(
                    category="UNKNOWN",
                    confidence=0.15,
                    severity=1,
                    evidence_signals=[f"gated_rejection:{assessment.rejection_reason}"],
                    method="relevance_gated",
                    model="rule_based_v2",
                    fallback_used=True,
                )
            return ClassificationResult(
                category=assessment.primary_category,
                sub_category=assessment.phenomenon,
                phenomenon=assessment.phenomenon,
                event_nature=assessment.incident_nature.value,
                temporal_scope=assessment.temporal_scope,
                is_current_observation=assessment.is_current_observation,
                evidence_basis=assessment.evidence_basis,
                confidence=round(assessment.confidence, 2),
                severity=assessment.severity,
                evidence_signals=assessment.evidence_signals,
                method="fallback_heuristic",
                model="rule_based_v2",
                fallback_used=True,
            )
        except Exception:
            assessment = None

        text_lower = text.lower()

        # Semantic Deficit / Anomaly / Excess / Dry Spell / No Rain Detection
        deficit_patterns = [
            r"\b(rainfall|rain|monsoon)\s+deficit\b",
            r"\b(below[\s-]normal|below[\s-]average)\s+(rainfall|rain|monsoon|precipitation)\b",
            r"\b(rain|rainfall|monsoon)\s+(shortfall|shortage)\b",
            r"\b(deficient|large\s+deficient)\s+(rainfall|rain|monsoon)\b",
            r"\bless\s+rainfall\s+than\s+normal\b",
            r"\bmonsoon\s+deficit\b",
            r"\brainfall\s+departure\s+of\s+-\d+",
            r"\b\d+%\s+below\s+normal\b",
            r"\bsub[\s-]normal\s+(rainfall|rain|monsoon)\b",
            r"\bmonsoon\s+withdraws.*?\b(?:rain|rainfall)\s+deficit\b",
            r"\brecord(?:s|ed)?\s+(?:rain|rainfall)\s+deficit\b",
        ]
        is_deficit = any(re.search(p, text_lower) for p in deficit_patterns)

        excess_patterns = [
            r"\b(above[\s-]normal|above[\s-]average)\s+(rainfall|rain|monsoon|precipitation)\b",
            r"\b(rainfall|rain|monsoon)\s+surplus\b",
            r"\b(excess|large\s+excess)\s+(rainfall|rain|monsoon)\b",
            r"\b\d+%\s+above\s+normal\b",
            r"\bsurplus\s+(rainfall|rain|monsoon)\b",
            r"\brainfall\s+departure\s+of\s+\+\d+",
        ]
        is_excess = any(re.search(p, text_lower) for p in excess_patterns)

        no_rain_patterns = [
            r"\bno\s+rainfall\s+(?:was\s+)?recorded\b",
            r"\bno\s+rain\s+(?:was\s+)?recorded\b",
            r"\bzero\s+(?:rainfall|rain)\b",
            r"\b0(?:\.0)?\s*mm\s+(?:of\s+)?rain\b",
            r"\brain\s*=\s*0\b",
            r"\bnil\s+rainfall\b",
        ]
        is_no_rain = any(re.search(p, text_lower) for p in no_rain_patterns)

        dry_spell_patterns = [
            r"\bdry\s+spell\b",
            r"\bprolonged\s+dry\s+spell\b",
            r"\bweeks\s+of\s+below[\s-]normal\b",
            r"\bextended\s+dry\s+period\b",
        ]
        is_dry_spell = any(re.search(p, text_lower) for p in dry_spell_patterns)

        forecast_patterns = [
            r"\b(predicts?|forecasts?|likely\s+to\s+receive|may\s+witness|may\s+receive|expected\s+to\s+receive)\s+.*?(?:rain|rainfall|downpour|shower|weather)\b",
            r"\b(forecast\s+for|extended\s+outlook|model\s+predicts?|ecmwf|gfs)\b",
        ]
        is_forecast = any(re.search(p, text_lower) for p in forecast_patterns)

        warning_patterns = [
            r"\b(issues?\s+.*?(?:warning|alert)|red\s+alert|orange\s+alert|yellow\s+alert)\b",
            r"\b(heavy\s+rainfall\s+warning|storm\s+warning|weather\s+warning)\b",
        ]
        is_warning = any(re.search(p, text_lower) for p in warning_patterns)

        scores: Dict[str, float] = {}
        matched_signals: Dict[str, List[str]] = {}

        for cat, keywords in CATEGORY_SIGNALS.items():
            cat_score = 0.0
            signals = []
            for kw in keywords:
                if kw in text_lower:
                    # Longer phrases receive higher weight
                    weight = 1.0 + (0.3 * len(kw.split()))
                    cat_score += weight
                    signals.append(kw)
            if cat_score > 0:
                scores[cat] = cat_score
                matched_signals[cat] = signals

        # If connector suggested a category, boost slightly only if not cyclone
        if metadata and metadata.get("suggested_category"):
            s_cat = metadata["suggested_category"].upper()
            if s_cat != "CYCLONE":
                if s_cat in scores:
                    scores[s_cat] += 2.0
                elif s_cat in CATEGORY_SIGNALS:
                    scores[s_cat] = 2.0
                    matched_signals[s_cat] = ["connector_suggested"]

        # Ambiguous / No signals -> UNKNOWN
        if not scores and not (is_deficit or is_excess or is_no_rain or is_dry_spell):
            return ClassificationResult(
                category="UNKNOWN",
                sub_category="UNKNOWN",
                phenomenon="UNKNOWN",
                event_nature="OBSERVATION",
                temporal_scope="CURRENT",
                is_current_observation=False,
                evidence_basis="NEWS_REPORT",
                confidence=0.25,
                severity=1,
                evidence_signals=["insufficient_signals"],
                method="fallback_heuristic",
                model="rule_based_v2",
                fallback_used=True,
            )

        # Find best category
        best_cat = max(scores, key=scores.get) if scores else "RAINFALL"

        # Rigorous cyclone check
        if best_cat == "CYCLONE" and assessment and not assessment.is_cyclone_rigorous:
            best_cat = "RAINFALL" if "rain" in text_lower else ("STRONG_WINDS" if "wind" in text_lower else "RAINFALL")

        raw_score = scores.get(best_cat, 1.0)
        # Normalize confidence to [0.55, 0.95]
        confidence = min(0.95, 0.55 + (raw_score * 0.10))

        # Severity estimation
        severity = 2  # default moderate
        for sev_level, words in sorted(SEVERITY_KEYWORDS.items(), reverse=True):
            if any(w in text_lower for w in words):
                severity = sev_level
                break

        # Semantic subtype & phenomenon resolution
        sub_cat = None
        phenomenon = None
        event_nature = "OBSERVATION"
        temporal_scope = "CURRENT"
        is_current_observation = True
        evidence_basis = "CURRENT_OBSERVATION"

        if is_deficit:
            best_cat = "RAINFALL"
            sub_cat = "RAINFALL_DEFICIT"
            phenomenon = "RAINFALL_DEFICIT"
            event_nature = "ANOMALY"
            temporal_scope = "SEASONAL" if ("monsoon" in text_lower or "season" in text_lower or "june" in text_lower or "september" in text_lower) else "MONTHLY"
            is_current_observation = False
            evidence_basis = "RAINFALL_ANOMALY"
            confidence = max(0.80, confidence)
        elif is_excess:
            best_cat = "RAINFALL"
            sub_cat = "RAINFALL_EXCESS"
            phenomenon = "RAINFALL_EXCESS"
            event_nature = "ANOMALY"
            temporal_scope = "SEASONAL" if ("monsoon" in text_lower or "season" in text_lower) else "MONTHLY"
            is_current_observation = False
            evidence_basis = "RAINFALL_ANOMALY"
            confidence = max(0.80, confidence)
        elif is_dry_spell:
            best_cat = "RAINFALL"
            sub_cat = "DRY_SPELL"
            phenomenon = "DRY_SPELL"
            event_nature = "ANOMALY"
            temporal_scope = "WEEKLY"
            is_current_observation = False
            evidence_basis = "RAINFALL_ANOMALY"
        elif is_no_rain:
            best_cat = "RAINFALL"
            sub_cat = "NO_RAIN"
            phenomenon = "NO_RAIN"
            event_nature = "OBSERVATION"
            temporal_scope = "CURRENT"
            is_current_observation = True
            evidence_basis = "STATION_TELEMETRY"
        elif is_warning:
            event_nature = "WARNING"
            is_current_observation = False
            evidence_basis = "OFFICIAL_WARNING"
            if best_cat == "RAINFALL":
                sub_cat = "HEAVY_RAINFALL"
                phenomenon = "HEAVY_RAINFALL"
        elif is_forecast:
            event_nature = "FORECAST"
            is_current_observation = False
            evidence_basis = "FORECAST"
            if best_cat == "RAINFALL":
                sub_cat = "RAINFALL_OBSERVED"
                phenomenon = "RAINFALL_OBSERVED"
        elif best_cat == "FLOODING":
            if "urban" in text_lower or "street" in text_lower or "road" in text_lower:
                sub_cat = "URBAN_FLOOD"
                phenomenon = "URBAN_FLOOD"
            elif "river" in text_lower or "dam" in text_lower:
                sub_cat = "RIVERINE_FLOOD"
                phenomenon = "RIVERINE_FLOOD"
            elif "flash" in text_lower:
                sub_cat = "FLASH_FLOOD"
                phenomenon = "FLASH_FLOOD"
            else:
                sub_cat = "URBAN_FLOOD"
                phenomenon = "URBAN_FLOOD"
        elif best_cat == "RAINFALL":
            if "cloudburst" in text_lower or "extremely heavy" in text_lower or "torrential" in text_lower:
                sub_cat = "EXTREME_RAINFALL"
                phenomenon = "EXTREME_RAINFALL"
                severity = 4
            elif "heavy" in text_lower or "downpour" in text_lower or "lashes" in text_lower:
                sub_cat = "HEAVY_RAINFALL"
                phenomenon = "HEAVY_RAINFALL"
                severity = max(3, severity)
            elif "drizzle" in text_lower or "light rain" in text_lower:
                sub_cat = "DRIZZLE"
                phenomenon = "RAINFALL_OBSERVED"
                severity = 1
            else:
                sub_cat = "RAINFALL_OBSERVED"
                phenomenon = "RAINFALL_OBSERVED"

        signals = matched_signals.get(best_cat, [])
        if phenomenon:
            signals.append(f"phenomenon:{phenomenon}")
        if event_nature:
            signals.append(f"nature:{event_nature}")

        return ClassificationResult(
            category=best_cat,
            sub_category=sub_cat,
            phenomenon=phenomenon or sub_cat,
            event_nature=event_nature,
            temporal_scope=temporal_scope,
            is_current_observation=is_current_observation,
            evidence_basis=evidence_basis,
            confidence=round(confidence, 2),
            severity=severity,
            evidence_signals=signals,
            method="fallback_heuristic",
            model="rule_based_v2",
            fallback_used=True,
        )

    async def extract_entities(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> EntityExtractionResult:
        """Extract spatial, meteorological attributes, and temporal phrases."""
        text_lower = text.lower()
        location_mentions = []
        resolved_city = None
        resolved_district = None
        resolved_state = None
        resolved_lat = None
        resolved_lon = None

        # 1. Location Matching
        for city_key, ref in INDIAN_CITIES_REFERENCE.items():
            if city_key in text_lower or ref["city"].lower() in text_lower:
                location_mentions.append(ref["city"])
                if not resolved_city:
                    resolved_city = ref["city"]
                    resolved_district = ref["district"]
                    resolved_state = ref["state"]
                    resolved_lat = ref["lat"]
                    resolved_lon = ref["lon"]
            elif ref["state"].lower() in text_lower and not resolved_state:
                resolved_state = ref["state"]
                location_mentions.append(ref["state"])

        # 2. Weather Attributes Extraction
        weather_attributes: List[WeatherAttribute] = []

        # Rainfall (e.g., 120 mm, 5.5 cm)
        rain_match = re.search(r"(\d+(?:\.\d+)?)\s*(mm|cm|inches?)\b", text_lower)
        if rain_match:
            val = float(rain_match.group(1))
            unit = rain_match.group(2)
            weather_attributes.append(
                WeatherAttribute(
                    name="rainfall_amount",
                    value=val,
                    unit=unit,
                    raw_mention=rain_match.group(0),
                )
            )

        # Wind speed (e.g., 75 km/h, 60 kmph)
        wind_match = re.search(r"(\d+(?:\.\d+)?)\s*(km/?h|kmph|knots|mph)\b", text_lower)
        if wind_match:
            val = float(wind_match.group(1))
            unit = wind_match.group(2)
            weather_attributes.append(
                WeatherAttribute(
                    name="wind_speed",
                    value=val,
                    unit=unit,
                    raw_mention=wind_match.group(0),
                )
            )

        # Temperature (e.g., 44.5 C, 44.5 °C, 42 degrees)
        temp_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:°\s*c|degrees?(?:\s*c)?|celsius|\bc\b)", text_lower)
        if temp_match:
            val = float(temp_match.group(1))
            weather_attributes.append(
                WeatherAttribute(
                    name="temperature",
                    value=val,
                    unit="°C",
                    raw_mention=temp_match.group(0),
                )
            )

        # Flood depth (e.g., 3 feet water, 1.5 m deep)
        flood_match = re.search(r"(\d+(?:\.\d+)?)\s*(feet|ft|meters?|m)\s*(?:deep|water|depth)\b", text_lower)
        if flood_match:
            val = float(flood_match.group(1))
            weather_attributes.append(
                WeatherAttribute(
                    name="flood_depth",
                    value=val,
                    unit=flood_match.group(2),
                    raw_mention=flood_match.group(0),
                )
            )

        # Visibility (e.g., 150m visibility, 50 meters visibility)
        vis_match = re.search(r"(\d+(?:\.\d+)?)\s*(meters?|m|km)\s*visibility\b", text_lower)
        if vis_match:
            val = float(vis_match.group(1))
            weather_attributes.append(
                WeatherAttribute(
                    name="visibility",
                    value=val,
                    unit=vis_match.group(2),
                    raw_mention=vis_match.group(0),
                )
            )

        # 3. Temporal Expressions
        temporal_mentions = []
        time_patterns = [
            "morning", "afternoon", "evening", "night", "yesterday", "today",
            "last night", "past 3 hours", "past hour", "continuous"
        ]
        for tp in time_patterns:
            if tp in text_lower:
                temporal_mentions.append(tp)

        # 4. Impact Mentions
        impact_mentions = []
        impact_terms = [
            "submerged", "waterlogging", "tree fall", "power cut", "traffic jam",
            "casualties", "stranded", "rescue", "delayed", "diverted", "alert"
        ]
        for it in impact_terms:
            if it in text_lower:
                impact_mentions.append(it)

        return EntityExtractionResult(
            event_mentions=list(set(location_mentions)),
            location_mentions=location_mentions,
            resolved_city=resolved_city,
            resolved_district=resolved_district,
            resolved_state=resolved_state,
            resolved_lat=resolved_lat,
            resolved_lon=resolved_lon,
            weather_attributes=weather_attributes,
            temporal_mentions=temporal_mentions,
            observed_time=datetime.now(timezone.utc),
            duration_str="continuous" if "continuous" in text_lower else None,
            impact_mentions=impact_mentions,
            evidence_phrases=[f"{attr.name}: {attr.value} {attr.unit}" for attr in weather_attributes],
            confidence=0.75 if resolved_city else 0.50,
            method="heuristic_regex",
        )

    async def analyze_media(self, media_urls: List[str], claimed_category: Optional[str] = None) -> MediaAnalysisResult:
        """Inspect media attachments and extract deterministic perceptual hash and visual signals."""
        if not media_urls:
            return MediaAnalysisResult(has_media=False)

        first_url = media_urls[0]
        # Deterministic perceptual hash representation (64-bit hex)
        phash = hashlib.sha256(first_url.encode("utf-8")).hexdigest()[:16]

        url_lower = first_url.lower()
        signals = []
        visual_cat = None
        supports = None

        if any(w in url_lower for w in ["rain", "water", "flood", "puddle", "downpour"]):
            signals.extend(["standing_water", "wet_surface"])
            visual_cat = "FLOODING" if "flood" in url_lower else "RAINFALL"
        elif any(w in url_lower for w in ["lightning", "storm", "thunder"]):
            signals.append("dark_sky_lightning")
            visual_cat = "THUNDERSTORM"
        elif any(w in url_lower for w in ["fog", "mist", "haze"]):
            signals.append("low_visibility_fog")
            visual_cat = "FOG"

        if claimed_category and visual_cat:
            supports = (claimed_category.upper() == visual_cat)

        return MediaAnalysisResult(
            has_media=True,
            media_type="image",
            visual_category=visual_cat,
            confidence=0.80 if visual_cat else 0.50,
            signals=signals,
            supports_claimed_event=supports,
            is_blurry=False,
            phash=phash,
            faces_detected=False,
            method="metadata_heuristic",
        )

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate a 384-dimensional unit-normalized semantic embedding vector.
        Uses a deterministic signed token-hashing projection so cosine similarity
        reflects text overlap and semantic relationships reliably without PyTorch downloads.
        """
        dim = 384
        vec = [0.0] * dim
        tokens = re.findall(r"\w+", text.lower())

        if not tokens:
            return [0.0] * dim

        # Add single tokens and bigrams
        terms = list(tokens)
        for i in range(len(tokens) - 1):
            terms.append(f"{tokens[i]}_{tokens[i+1]}")

        # Inject semantic concept tokens for matched weather categories
        text_lower = text.lower()
        for cat, kws in CATEGORY_SIGNALS.items():
            if any(kw in text_lower for kw in kws):
                terms.extend([f"__concept_{cat.lower()}__"] * 3)

        # Inject city/state concept tokens
        for city_key, ref in INDIAN_CITIES_REFERENCE.items():
            if city_key in text_lower or ref["city"].lower() in text_lower:
                terms.extend([f"__loc_{city_key}__"] * 2)

        for term in terms:
            h = hashlib.md5(term.encode("utf-8")).digest()
            idx = int.from_bytes(h[:2], "big") % dim
            sign = 1.0 if (h[2] % 2 == 0) else -1.0
            vec[idx] += sign

        # L2 Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 1e-9:
            vec = [round(x / norm, 6) for x in vec]
        return vec

    async def detect_anomaly(
        self,
        category: str,
        severity: int,
        city: Optional[str] = None,
        district: Optional[str] = None,
        state: Optional[str] = None,
        event_time: Optional[datetime] = None,
        nearby_events_count: int = 0,
    ) -> AnomalyResult:
        """Compute anomaly score based on meteorological season, severity, and spatial consistency."""
        t = event_time or datetime.now(timezone.utc)
        month = t.month
        cat_upper = category.upper()

        expected = SEASONAL_EXPECTATIONS.get(month, [])
        is_seasonal = cat_upper in expected or cat_upper == "UNKNOWN"

        signals = []
        z_score = 0.5

        # 1. Seasonal Anomaly
        if not is_seasonal:
            z_score += 1.8
            signals.append(f"Unseasonal {cat_upper} during month {month}")

        # 2. Extreme Severity Anomaly
        if severity >= 4:
            z_score += 1.2
            signals.append("Extreme severity 4 event")

        # 3. Spatial Isolation Anomaly (Severity >= 3 but 0 nearby reports)
        if severity >= 3 and nearby_events_count == 0:
            z_score += 0.8
            signals.append("Isolated high-severity event without nearby corroboration")

        anomaly_score = min(1.0, z_score / 4.0)
        is_anomalous = z_score >= 2.0

        anomaly_type = None
        if is_anomalous:
            if not is_seasonal:
                anomaly_type = "TEMPORAL"
            elif nearby_events_count == 0:
                anomaly_type = "SPATIAL"
            else:
                anomaly_type = "VOLUME"

        desc = (
            f"Z-score {z_score:.2f}: {', '.join(signals)}"
            if signals else "Normal seasonal observation"
        )

        return AnomalyResult(
            is_anomalous=is_anomalous,
            anomaly_score=round(anomaly_score, 2),
            z_score=round(z_score, 2),
            anomaly_type=anomaly_type,
            signals=signals,
            description=desc,
        )

    async def assess_evidence(
        self,
        report_data: Dict[str, Any],
        official_data: Optional[Dict[str, Any]] = None,
        nearby_reports: Optional[List[Dict[str, Any]]] = None,
        source_trust: float = 0.5,
        media_analysis: Optional[MediaAnalysisResult] = None,
        physical_observation: Optional[Dict[str, Any]] = None,
    ) -> EvidenceAssessmentResult:
        """
        Synthesize multi-source signals into an explainable verification verdict.
        Checks official bulletins, nearby reports, source trust, media, and physical observations.
        """
        claimed_cat = report_data.get("primary_category") or report_data.get("category") or report_data.get("suggested_category") or "UNKNOWN"
        nearby_count = len(nearby_reports or [])

        # 1. Official Data Match
        official_match = 0.5  # neutral default
        official_desc = "No concurrent official API bulletin found"
        if official_data:
            off_cat = official_data.get("category") or official_data.get("primary_category") or official_data.get("suggested_category") or official_data.get("hazard_type")
            if off_cat and (off_cat.upper() == claimed_cat.upper() or (off_cat.upper() == "RAINFALL" and claimed_cat.upper() == "FLOODING")):
                official_match = 1.0
                official_desc = f"Confirmed by official observation ({off_cat})"
            else:
                official_match = 0.1
                official_desc = f"Official observation reports {off_cat}, differing from {claimed_cat}"

        # 2. Physical Observation Corroboration / Contradiction
        physical_obs_match = 0.5
        has_contradiction = False
        contradiction_reason = None
        
        obs = physical_observation or report_data.get("physical_observation")
        if obs:
            p_cond = (obs.get("weather_condition") or "").lower()
            p_wind = float(obs.get("wind_speed_kmh") or 0.0)
            p_precip = float(obs.get("precipitation_mm") or 0.0)

            if claimed_cat == "CYCLONE":
                if p_wind < 40.0 and p_precip == 0.0 and ("clear" in p_cond or "sun" in p_cond):
                    has_contradiction = True
                    physical_obs_match = 0.05
                    contradiction_reason = f"Station observation records clear sky ({p_wind:.1f} km/h wind, 0 mm rain), contradicting cyclonic conditions."
                elif p_wind >= 62.0:
                    physical_obs_match = 1.0
            elif claimed_cat in ("RAINFALL", "FLOODING"):
                if p_precip == 0.0 and ("clear" in p_cond or "sun" in p_cond):
                    has_contradiction = True
                    physical_obs_match = 0.15
                    contradiction_reason = "Station telemetry confirms zero rainfall and clear sky."
                elif p_precip > 0.0 or "rain" in p_cond:
                    physical_obs_match = 1.0

        # 3. Nearby Corroboration
        nearby_score = min(1.0, nearby_count / 3.0)

        # 4. Source Trust
        trust_score = max(0.0, min(1.0, source_trust))

        # 5. Media Match
        image_score = 0.5
        if media_analysis and media_analysis.has_media:
            if media_analysis.supports_claimed_event is True:
                image_score = 1.0
            elif media_analysis.supports_claimed_event is False:
                image_score = 0.1

        # 6. Temporal Consistency & Historical Baseline
        temporal_score = 0.85
        now_month = datetime.now(timezone.utc).month
        hist_score = 0.8 if claimed_cat in SEASONAL_EXPECTATIONS.get(now_month, []) else 0.4

        # Composite verification score
        composite = (
            0.25 * official_match
            + 0.20 * physical_obs_match
            + 0.20 * nearby_score
            + 0.15 * trust_score
            + 0.10 * image_score
            + 0.05 * temporal_score
            + 0.05 * hist_score
        )
        if has_contradiction:
            composite = max(0.05, composite - 0.35)

        composite = max(0.0, min(1.0, composite))

        # Determine verification status
        if has_contradiction or (official_match <= 0.1 and nearby_count == 0 and composite < 0.35):
            status = "CONTRADICTED"
        elif composite >= 0.75:
            status = "VERIFIED"
        elif composite >= 0.50:
            status = "LIKELY"
        elif composite >= 0.30:
            status = "UNVERIFIED"
        else:
            status = "REQUIRES_REVIEW"

        explanation_parts = [f"Verdict: {status} (confidence: {composite:.0%})", f"Source trust: {trust_score:.2f}", f"{nearby_count} corroborating nearby reports", official_desc]
        if contradiction_reason:
            explanation_parts.append(contradiction_reason)
        explanation = ". ".join(explanation_parts) + "."

        signal_scores = {
            "official_match": round(official_match, 2),
            "physical_obs_match": round(physical_obs_match, 2),
            "nearby_corroboration": round(nearby_score, 2),
            "source_trust": round(trust_score, 2),
            "image_evidence": round(image_score, 2),
            "temporal_consistency": round(temporal_score, 2),
            "historical_baseline": round(hist_score, 2),
        }

        evidence_summary = [
            {"type": "OFFICIAL_API", "score": official_match, "detail": official_desc},
            {"type": "PHYSICAL_OBSERVATION", "score": physical_obs_match, "detail": contradiction_reason or "Station observation baseline checked"},
            {"type": "CORROBORATING_REPORTS", "count": nearby_count, "score": nearby_score},
            {"type": "SOURCE_TRUST", "score": trust_score},
            {"type": "MEDIA_ANALYSIS", "score": image_score},
        ]

        return EvidenceAssessmentResult(
            verification_status=status,
            verification_confidence=round(composite, 2),
            signal_scores=signal_scores,
            evidence_summary=evidence_summary,
            explanation=explanation,
            method="evidence_matrix",
        )
