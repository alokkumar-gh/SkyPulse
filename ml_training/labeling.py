"""
SkyPulse Dataset Labeling & Conflict Resolution Pipeline.
=========================================================
Applies conservative meteorological labeling rules to classify raw observations
into strong labels, weak labels, or unlabeled instances, resolving cross-source conflicts.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from ml.schemas import WeatherEventCategory, LabelType, TrainingRecord

logger = logging.getLogger("skypulse.ml.labeling")

# Conservative Meteorological Thresholds
METEOROLOGICAL_THRESHOLDS = {
    "HEAVY_RAINFALL_MM": 64.5,       # IMD threshold for Heavy Rainfall (64.5 - 115.5 mm)
    "VERY_HEAVY_RAINFALL_MM": 115.6, # IMD threshold for Very Heavy Rainfall
    "EXTREME_RAINFALL_MM": 204.5,    # IMD threshold for Extremely Heavy Rainfall
    "HEATWAVE_PLAINS_TEMP_C": 45.0,  # IMD threshold for severe heat in plains
    "GALE_WIND_KMH": 62.0,           # IMD threshold for gale/squall wind
    "DENSE_FOG_VISIBILITY_M": 200.0, # IMD threshold for dense fog (< 200m)
}


class LabelingEngine:
    """
    Evaluates raw report payloads, texts, and source evidence to generate traceable labels.
    """

    @staticmethod
    def derive_label(
        text: str,
        source_type: str,
        raw_payload: Optional[Dict[str, Any]] = None,
        verified_status: Optional[str] = None,
        source_trust: float = 0.5,
    ) -> Tuple[WeatherEventCategory, LabelType, str, float, List[str], bool]:
        """
        Derives event category, label type (STRONG/WEAK/UNLABELED), method, confidence,
        candidate labels, and conflict flag.
        """
        payload = raw_payload or {}
        text_lower = (text or "").lower()
        candidates: List[str] = []

        # 1. Inspect Explicit Warnings & Authoritative Government Signals (STRONG)
        is_official_gov = source_type.upper() in ("GOVERNMENT_API", "IMD", "DATA_GOV_IN", "GOVERNMENT_DATASET")
        warning_cat = payload.get("warning_category") or payload.get("hazard_type")
        if warning_cat and is_official_gov:
            cat_norm = str(warning_cat).upper().strip()
            if cat_norm in WeatherEventCategory._value2member_map_:
                return (
                    WeatherEventCategory(cat_norm),
                    LabelType.STRONG,
                    "OFFICIAL_GOVERNMENT_WARNING",
                    0.95,
                    [cat_norm],
                    False,
                )

        # 2. Check Verified SkyPulse Ground Events (STRONG)
        if verified_status in ("VERIFIED", "SUPPORTED") and source_trust >= 0.75:
            # Look for strong primary event in payload
            claimed_cat = payload.get("primary_category") or payload.get("category")
            if claimed_cat:
                c_str = str(claimed_cat).upper().strip()
                if c_str in WeatherEventCategory._value2member_map_ and c_str != "UNKNOWN":
                    return (
                        WeatherEventCategory(c_str),
                        LabelType.STRONG,
                        "VERIFIED_GROUND_CORROBORATION",
                        0.90,
                        [c_str],
                        False,
                    )

        # 3. Check Meteorological Sensor Thresholds (WEAK)
        rain_mm = payload.get("rainfall_mm") or payload.get("precipitation_mm")
        temp_c = payload.get("temperature_c") or payload.get("max_temp_c")
        wind_kmh = payload.get("wind_speed_kmh") or payload.get("wind_kmph")
        visibility_m = payload.get("visibility_m") or payload.get("visibility_meters")

        if rain_mm is not None and rain_mm >= METEOROLOGICAL_THRESHOLDS["HEAVY_RAINFALL_MM"]:
            candidates.append(WeatherEventCategory.RAINFALL.value)
        if temp_c is not None and temp_c >= METEOROLOGICAL_THRESHOLDS["HEATWAVE_PLAINS_TEMP_C"]:
            candidates.append(WeatherEventCategory.HEATWAVE.value)
        if wind_kmh is not None and wind_kmh >= METEOROLOGICAL_THRESHOLDS["GALE_WIND_KMH"]:
            candidates.append(WeatherEventCategory.STRONG_WINDS.value)
        if visibility_m is not None and visibility_m <= METEOROLOGICAL_THRESHOLDS["DENSE_FOG_VISIBILITY_M"]:
            candidates.append(WeatherEventCategory.FOG.value)

        # 4. Textual Keyword Evidence Analysis
        import re

        def _has_kw(keywords: List[str]) -> bool:
            for kw in keywords:
                if " " in kw:
                    if kw in text_lower:
                        return True
                else:
                    if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                        return True
            return False

        text_matches = []
        if _has_kw(["cyclone", "cyclonic storm", "depression", "chakravat"]):
            text_matches.append(WeatherEventCategory.CYCLONE.value)
        if _has_kw(["flood", "flooding", "waterlogged", "waterlogging", "inundated", "submerged", "barh"]):
            text_matches.append(WeatherEventCategory.FLOODING.value)
        if _has_kw(["thunderstorm", "lightning", "bijli", "thunderclap", "tufan"]):
            text_matches.append(WeatherEventCategory.THUNDERSTORM.value)
        if _has_kw(["heatwave", "heat wave", "extreme heat", "loo", "scorching"]):
            text_matches.append(WeatherEventCategory.HEATWAVE.value)
        if _has_kw(["dust storm", "duststorm", "sandstorm", "haboob", "aandhi"]):
            text_matches.append(WeatherEventCategory.DUST_STORM.value)
        if _has_kw(["fog", "dense fog", "mist", "dhund", "kohra"]):
            text_matches.append(WeatherEventCategory.FOG.value)
        if _has_kw(["heavy rain", "rainfall", "downpour", "torrential rain", "cloudburst", "baarish"]):
            text_matches.append(WeatherEventCategory.RAINFALL.value)
        if _has_kw(["strong wind", "gale", "high winds", "gusty winds", "squall"]):
            text_matches.append(WeatherEventCategory.STRONG_WINDS.value)
        if _has_kw(["hailstorm", "hail", "olavrishti"]):
            text_matches.append(WeatherEventCategory.HAILSTORM.value)
        if _has_kw(["snowfall", "snow", "barfbari"]):
            text_matches.append(WeatherEventCategory.SNOWFALL.value)
        if _has_kw(["smog", "air pollution", "pm2.5", "hazardous air"]):
            text_matches.append(WeatherEventCategory.SMOG.value)

        for tm in text_matches:
            if tm not in candidates:
                candidates.append(tm)


        # Include candidate_labels from payload if provided
        for cand in payload.get("candidate_labels", []):
            cand_norm = str(cand).upper().strip()
            if cand_norm in WeatherEventCategory._value2member_map_ and cand_norm not in candidates:
                candidates.append(cand_norm)

        # 5. Resolve Conflicts and Assign Final Category
        has_conflict = False
        if len(candidates) == 0:
            return (
                WeatherEventCategory.UNKNOWN,
                LabelType.UNLABELED,
                "UNLABELED_INSUFFICIENT_SIGNALS",
                0.30,
                [],
                False,
            )

        if len(candidates) == 1:
            chosen = WeatherEventCategory(candidates[0])
            is_strong = is_official_gov or verified_status == "VERIFIED"
            conf = 0.95 if is_strong else 0.80
            method = "OFFICIAL_GOVERNMENT_WARNING" if is_strong else "METEOROLOGICAL_SIGNAL_MATCH"
            if "METEOROLOGICAL_THRESHOLD" in method or rain_mm or temp_c or wind_kmh or visibility_m:
                if rain_mm and rain_mm >= METEOROLOGICAL_THRESHOLDS["HEAVY_RAINFALL_MM"]:
                    method = "METEOROLOGICAL_THRESHOLD_HEAVY_RAIN"
            return (
                chosen,
                LabelType.STRONG if is_strong else LabelType.WEAK,
                method,
                conf,
                candidates,
                False,
            )

        # Multiple candidate categories: Check if hierarchically compatible
        cand_set = set(candidates)
        if WeatherEventCategory.CYCLONE.value in cand_set and WeatherEventCategory.RAINFALL.value in cand_set:
            is_strong = is_official_gov or verified_status == "VERIFIED"
            return (
                WeatherEventCategory.CYCLONE,
                LabelType.STRONG if is_strong else LabelType.WEAK,
                "CYCLONIC_WARNING_PRECIPITATION",
                0.95 if is_strong else 0.85,
                candidates,
                False,
            )
        elif cand_set == {WeatherEventCategory.FLOODING.value, WeatherEventCategory.RAINFALL.value}:
            # Explicit flood mentions take precedence over rainfall
            return (
                WeatherEventCategory.FLOODING,
                LabelType.WEAK,
                "COMPATIBLE_MULTI_SIGNAL_FLOOD_RAIN",
                0.80,
                candidates,
                True,
            )
        elif cand_set == {WeatherEventCategory.THUNDERSTORM.value, WeatherEventCategory.STRONG_WINDS.value}:
            return (
                WeatherEventCategory.THUNDERSTORM,
                LabelType.WEAK,
                "COMPATIBLE_MULTI_SIGNAL_STORM_WIND",
                0.80,
                candidates,
                False,
            )
        elif cand_set == {WeatherEventCategory.THUNDERSTORM.value, WeatherEventCategory.RAINFALL.value}:
            return (
                WeatherEventCategory.THUNDERSTORM,
                LabelType.WEAK,
                "COMPATIBLE_MULTI_SIGNAL_STORM_RAIN",
                0.80,
                candidates,
                False,
            )
        else:
            # Genuine conflicting signals -> Conflict flag set
            has_conflict = True
            return (
                WeatherEventCategory.UNKNOWN,
                LabelType.UNLABELED,
                "CONFLICTING_OBSERVATION_SIGNALS",
                0.20,
                candidates,
                has_conflict,
            )

    def process_record(self, record: TrainingRecord) -> TrainingRecord:
        """
        Derives and updates label metadata, candidates, and conflict flag on a TrainingRecord.
        """
        payload = dict(record.metadata or {})
        if record.candidate_labels:
            payload["candidate_labels"] = record.candidate_labels

        cat, label_type, method, conf, candidates, conflict = self.derive_label(
            text=record.text,
            source_type=record.source_type,
            raw_payload=payload,
            verified_status=record.verification_status,
            source_trust=0.95 if record.verified or record.source_type == "IMD" else 0.60,
        )

        record.category = cat
        record.label_source = record.label_source or (
            "IMD_WARNING" if record.source_type == "IMD" else f"{record.source_type}_OBSERVATION"
        )
        record.label_confidence = conf
        record.label_method = method
        record.conflict_flag = conflict
        record.candidate_labels = candidates
        meta = record.metadata or {}
        meta["label_type"] = label_type.value
        record.metadata = meta
        return record



labeling_engine = LabelingEngine()

