"""
SkyPulse National Weather Relevance & Gating Engine
====================================================
Provides multi-dimensional relevance gating, false positive protection,
source authority tiering, rigorous hazard classification (especially CYCLONE gating),
meteorological plausibility validation, and inland storm lineage tracking.

Applies across all Indian states and meteorological regions without hardcoded location bans.
"""

import re
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("skypulse.weather_relevance_engine")


class IncidentNature(str, Enum):
    CURRENT_OBSERVATION = "OBSERVATION"  # Active ongoing event / damage / precipitation
    SEASONAL_ANOMALY = "ANOMALY"        # Deficit, surplus, or climate departure
    OFFICIAL_WARNING = "WARNING"        # Active IMD / CWC / NDMA alert in validity window
    FORECAST_POTENTIAL = "FORECAST"    # Future system / potential formation / forecast
    HISTORICAL_STUDY = "RETROSPECTIVE"  # Retrospective analysis / past events / history
    NON_WEATHER_DRILL = "NON_WEATHER_DRILL"      # Mock drills, policy, infrastructure, metaphors
    UNVERIFIED_SIGNAL = "OBSERVATION"      # Single citizen / uncorroborated social report


class SourceAuthorityTier(int, Enum):
    TIER_1_OFFICIAL = 1       # IMD, CWC, NDMA, SACHET, Government Bulletins, Official CAP Feeds
    TIER_2_SCIENTIFIC = 2     # Doppler Weather Radar, River Gauges, ECMWF, GFS, Met Stations (AWS)
    TIER_3_VERIFIED_NEWS = 3  # The Hindu, PTI, ANI, Times of India, Indian Express, Hindustan Times, PIB
    TIER_4_REGIONAL_MEDIA = 4 # Regional language news, local media portals
    TIER_5_CITIZEN_SOCIAL = 5 # Citizen ground reports, social media posts, unverified web posts


class CyclonicStage(str, Enum):
    ACTIVE_CYCLONE = "ACTIVE_CYCLONE"
    LANDFALL_UNDERWAY = "LANDFALL_UNDERWAY"
    POST_LANDFALL_CYCLONE = "POST_LANDFALL_CYCLONE"
    DEEP_DEPRESSION = "DEEP_DEPRESSION"
    DEPRESSION = "DEPRESSION"
    LOW_PRESSURE_AREA = "LOW_PRESSURE_AREA"
    REMNANT_CIRCULATION = "REMNANT_CIRCULATION"
    CYCLONE_WARNING_ADVISORY = "CYCLONE_WARNING_ADVISORY"
    CYCLONE_CANDIDATE_UNCONFIRMED = "CYCLONE_CANDIDATE_UNCONFIRMED"


class RelevanceAssessment:
    """Detailed evaluation result for a weather signal/report."""

    def __init__(
        self,
        is_relevant: bool,
        incident_nature: IncidentNature,
        primary_category: str,
        confidence: float,
        severity: int,
        is_cyclone_rigorous: bool,
        rejection_reason: Optional[str] = None,
        location_specificity: str = "EXPLICIT",  # EXPLICIT, REGIONAL_ONLY, AMBIGUOUS
        evidence_signals: Optional[List[str]] = None,
        authority_tier: SourceAuthorityTier = SourceAuthorityTier.TIER_3_VERIFIED_NEWS,
        phenomenon: Optional[str] = None,
        temporal_scope: str = "CURRENT",
        is_current_observation: bool = True,
        evidence_basis: str = "CURRENT_OBSERVATION",
        cyclonic_stage: Optional[str] = None,
        lineage_system_id: Optional[str] = None,
        is_inland_system: bool = False,
    ):
        self.is_relevant = is_relevant
        self.incident_nature = incident_nature
        self.primary_category = primary_category
        self.confidence = confidence
        self.severity = severity
        self.is_cyclone_rigorous = is_cyclone_rigorous
        self.rejection_reason = rejection_reason
        self.location_specificity = location_specificity
        self.evidence_signals = evidence_signals or []
        self.authority_tier = authority_tier
        self.phenomenon = phenomenon or primary_category
        self.temporal_scope = temporal_scope
        self.is_current_observation = is_current_observation
        self.evidence_basis = evidence_basis
        self.cyclonic_stage = cyclonic_stage
        self.lineage_system_id = lineage_system_id
        self.is_inland_system = is_inland_system

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_relevant": self.is_relevant,
            "incident_nature": self.incident_nature.value,
            "primary_category": self.primary_category,
            "phenomenon": self.phenomenon,
            "temporal_scope": self.temporal_scope,
            "is_current_observation": self.is_current_observation,
            "evidence_basis": self.evidence_basis,
            "confidence": round(self.confidence, 2),
            "severity": self.severity,
            "is_cyclone_rigorous": self.is_cyclone_rigorous,
            "cyclonic_stage": self.cyclonic_stage,
            "lineage_system_id": self.lineage_system_id,
            "is_inland_system": self.is_inland_system,
            "rejection_reason": self.rejection_reason,
            "location_specificity": self.location_specificity,
            "evidence_signals": self.evidence_signals,
            "authority_tier": self.authority_tier.value,
        }


# ---------------------------------------------------------------------------
# Negative Patterns (False Positives, Drills, Policy, Metaphors)
# ---------------------------------------------------------------------------

_METAPHOR_PATTERNS = [
    re.compile(r"\b(political|parliamentary|assembly|cabinet|bjp|congress|aap|court)\s+(storm|firestorm|heat|wave)\b", re.IGNORECASE),
    re.compile(r"\b(storm|firestorm)\s+(in|hits|inside|rocks|shakes|roils|engulfs|among|at)\s+(parliament|lok\s+sabha|rajya\s+sabha|assembly|politics|court|ministry|investors?|markets?|traders?|box\s+office)\b", re.IGNORECASE),
    re.compile(r"\b(stock\s+market|market\s+crash|share\s+market|sensex|nifty|bollywood|movie|film|box\s+office)\s+.*?\b(storm|heat|wave)\b", re.IGNORECASE),
    re.compile(r"\bflood\s+of\s+(applications?|complaints?|wishes?|tributes?|congratulations?|messages?|memes?|reactions?|queries|tickets?)\b", re.IGNORECASE),
    re.compile(r"\b(wave|flood)\s+of\s+(protests?|criticism|anger|strikes?)\b", re.IGNORECASE),
    re.compile(r"\b(brainstorm|brainstorming|teacup)\b", re.IGNORECASE),
]

_DRILL_AND_NON_EVENT_PATTERNS = [
    re.compile(r"\b(mock\s+drill|preparedness\s+drill|cyclone\s+drill|evacuation\s+drill|tabletop\s+exercise|simulation\s+exercise)\b", re.IGNORECASE),
    re.compile(r"\b(awareness\s+campaign|awareness\s+rally|poster\s+competition|essay\s+competition)\b", re.IGNORECASE),
    re.compile(r"\b(telecom\s+towers?|mobile\s+towers?|optical\s+fibre)\s+.*?\b(risk|vulnerable|study|report)\b", re.IGNORECASE),
    re.compile(r"\b(delays?\s+.*?\bradars?|procurement\s+of\s+radar|radar\s+maintenance|radar\s+down)\b", re.IGNORECASE),
    re.compile(r"\b(cloud\s+chasers?|storm\s+chasers?\s+club|photographers?\s+group)\b", re.IGNORECASE),
]

_HISTORICAL_AND_RETROSPECTIVE_PATTERNS = [
    re.compile(r"\b(why\s+do\s+cyclones?\s+keep\s+hitting|history\s+of\s+cyclones?|past\s+cyclones?|historic\s+(?:super\s+)?cyclones?|remembering\s+the)\b", re.IGNORECASE),
    re.compile(r"\b(1999\s+super\s+cyclone|super\s+cyclone\s+of\s+1999|fani\s+anniversary|hudhud\s+anniversary|amphan\s+anniversary)\b", re.IGNORECASE),
    re.compile(r"\b(blueprint\s+for|lessons?\s+from\s+past|how\s+.*?\bbecame\s+the\s+blueprint)\b", re.IGNORECASE),
    re.compile(r"\b(decade\s+ago|years?\s+ago|in\s+the\s+past|anniversary\s+of)\b", re.IGNORECASE),
    re.compile(r"\b(cyclone-prone|flood-prone|drought-prone|disaster-prone)\s+.*?\b(study|analyzes?|explains?|research|history)\b", re.IGNORECASE),
    re.compile(r"\b(study|research)\s+.*?\b(cyclone-prone|flood-prone)\b", re.IGNORECASE),
]

_FORECAST_AND_SPECULATION_PATTERNS = [
    re.compile(r"\b(no\s+prediction\s+on\s+cyclone|rules?\s+out\s+cyclone|no\s+cyclone\s+threat|no\s+cyclone\s+warning)\b", re.IGNORECASE),
    re.compile(r"\b(will\s+it\s+become\s+cyclone|may\s+intensify|likely\s+to\s+form|may\s+form|possibility\s+of\s+cyclone)\b", re.IGNORECASE),
    re.compile(r"\b(cyclonic\s+circulation\s+likely|system\s+may\s+develop|depression\s+expected\s+to)\b", re.IGNORECASE),
    re.compile(r"\b(forecast\s+for\s+next\s+week|extended\s+outlook|model\s+suggests?|ecmwf\s+predicts?|gfs\s+shows?)\b", re.IGNORECASE),
]

_OFFICIAL_WARNING_PATTERNS = [
    re.compile(r"\b(imd\s+issues?|red\s+alert|orange\s+alert|yellow\s+alert|flood\s+warning|cwc\s+bulletin|sachet\s+alert|flash\s+flood\s+guidance)\b", re.IGNORECASE),
    re.compile(r"\b(warning\s+issued\s+for|heavy\s+rainfall\s+warning|storm\s+warning\s+bulletin|landfall\s+warning)\b", re.IGNORECASE),
]

_CURRENT_OBSERVATION_PATTERNS = [
    re.compile(r"\b(inundat|submerged|waterlogg|cloudburst|heavy\s+downpour|torrential\s+rain|flash\s+flood\s+hits|landslide\s+blocked)\b", re.IGNORECASE),
    re.compile(r"\b(trees?\s+uprooted|traffic\s+halted|flights?\s+diverted|trains?\s+cancelled|water\s+level\s+crossed|record\s+rainfall|mm\s+rain\s+recorded)\b", re.IGNORECASE),
    re.compile(r"\b(landfall\s+underway|made\s+landfall|landfall\s+near|cyclone\s+crosses|eye\s+of\s+cyclone|gusts?\s+clocked)\b", re.IGNORECASE),
]

_OFFICIAL_CYCLONE_BULLETIN_PATTERNS = [
    re.compile(r"\b(imd\s+cyclone\s+bulletin|national\s+bulletin\s+no\.|cyclonic\s+storm\s+['\"][A-Za-z]+['\"]|severe\s+cyclonic\s+storm\s+['\"][A-Za-z]+['\"]|very\s+severe\s+cyclonic\s+storm|super\s+cyclonic\s+storm|landfall\s+process\s+commenced|eye\s+of\s+the\s+cyclonic\s+storm)\b", re.IGNORECASE),
    re.compile(r"\b(depression\s+concentrated\s+into\s+cyclonic\s+storm|deep\s+depression\s+intensified\s+into\s+cyclonic\s+storm)\b", re.IGNORECASE),
    re.compile(r"\b(cyclone\s+warning|red\s+cyclone\s+warning|cyclone\s+alert|severe\s+storm\s+approaches|tropical\s+cyclone|landfall\s+near|made\s+landfall)\b", re.IGNORECASE),
]

_POLITICAL_CRIME_AND_CIVIL_PATTERNS = [
    re.compile(r"\b(police\s+files?\s+fir|registered\s+fir|lodged\s+fir|case\s+filed\s+over\s+protest|chargesheet|arrested|in\s+police\s+custody|bail\s+plea|high\s+court|supreme\s+court)\b", re.IGNORECASE),
    re.compile(r"\b(protest\s+held|protests?\s+at|save\s+democracy|election\s+commission|political\s+rally|protest\s+rally|stage\s+protest|hunger\s+strike|demonstration\s+against)\b", re.IGNORECASE),
    re.compile(r"\b(murder|robbery|scam|corruption|cbi\s+probe|ed\s+raids?|interrogation)\b", re.IGNORECASE),
]

_GENUINE_METEOROLOGICAL_TERMS = re.compile(
    r"\b(rain|rainfall|monsoon|downpour|shower|drizzle|precipitation|waterlog|inundat|flood|flooding|cloudburst|"
    r"cyclone|cyclonic|depression|typhoon|storm|thunder|lightning|heatwave|heat\s+wave|temperature|cold\s+wave|"
    r"coldwave|fog|smog|visibility|hail|hailstorm|landslide|mudslide|drought|dry\s+spell|deficit|surplus|shortfall|"
    r"gale|squall|winds?|gusts?|clouds?|weather|"
    r"imd|cwc|ndma|sachet|doppler|radar|barometer|relative\s+humidity)\b|"
    r"(बारिश|वर्षा|बाढ़|तूफान|चक्रवात|लू|गर्मी|धुंध|कोहरा|मौसम|बादल|"
    r"ବର୍ଷା|ଘୂର୍ଣ୍ଣିବାତ|ବନ୍ୟା|ବାତ୍ୟା|କୁହୁଡ଼ି|ପ୍ରବଳ|"
    r"বৃষ্টি|ঘূর্ণিঝড়|বন্যা|ঝড়|"
    r"மழை|புயல்|வெள்ளம்|"
    r"వర్షం|తుఫాను|వరద|"
    r"മഴ|ചുഴലിക്കാറ്റ്|വെള്ളപ്പൊക്കം|"
    r"पाऊस|पूर|वादळ|चक्रीवादळ|"
    r"વરસાદ|પૂર|વાવાઝોડું|"
    r"ਮੀਂਹ|ਹੜ੍ਹ|ਤੂਫ਼ਾਨ)",
    re.IGNORECASE
)


class WeatherRelevanceEngine:
    """
    Central, domain-grounded national relevance and meteorological validation engine.
    Ensures that only authentic, active, grounded meteorological events are published.
    Protects against false cyclone classifications, ungrounded severity inflation,
    and pseudo multi-source assertions.
    """

    @classmethod
    def evaluate(
        cls,
        text: str,
        title: Optional[str] = None,
        source_name: Optional[str] = None,
        source_type: Optional[str] = None,
        claimed_category: Optional[str] = None,
        has_gps: bool = False,
        published_at: Optional[str] = None,
        location_state: Optional[str] = None,
        location_district: Optional[str] = None,
        observed_telemetry: Optional[Dict[str, Any]] = None,
        tracked_parent_system_id: Optional[str] = None,
    ) -> RelevanceAssessment:
        """
        Evaluate full relevance, incident nature, category rigor, authority tiering,
        and geographic/meteorological plausibility.
        """
        combined = f"{title or ''} {text or ''}".strip()
        low = combined.lower()

        # 1. Authority Tier Detection
        src_str = f"{source_name or ''} {source_type or ''}".lower()
        if any(kw in src_str for kw in ("imd", "cwc", "ndma", "sachet", "official", "government", "bulletin", "cap_alert")):
            authority_tier = SourceAuthorityTier.TIER_1_OFFICIAL
        elif any(kw in src_str for kw in ("radar", "satellite", "gauge", "telemetry", "station", "met_", "openmeteo", "aws", "era5")):
            authority_tier = SourceAuthorityTier.TIER_2_SCIENTIFIC
        elif any(kw in src_str for kw in ("the hindu", "the_hindu", "pti", "ani", "times of india", "indian express", "hindustan times", "ndtv", "pib")):
            authority_tier = SourceAuthorityTier.TIER_3_VERIFIED_NEWS
        elif any(kw in src_str for kw in ("citizen", "public", "user_report", "crowdsourced")):
            authority_tier = SourceAuthorityTier.TIER_5_CITIZEN_SOCIAL
        else:
            authority_tier = SourceAuthorityTier.TIER_4_REGIONAL_MEDIA

        # 2. Metaphor & Non-Weather Check
        has_concrete_met_evidence = bool(re.search(r"\b(\d+\s*mm|rainfall|waterlogging|cyclone\s+approaches|flood\s+warning|red\s+alert|landfall)\b", low))
        for pat in _METAPHOR_PATTERNS:
            if pat.search(low) and not has_concrete_met_evidence:
                return RelevanceAssessment(
                    is_relevant=False,
                    incident_nature=IncidentNature.NON_WEATHER_DRILL,
                    primary_category="UNKNOWN",
                    confidence=0.1,
                    severity=1,
                    is_cyclone_rigorous=False,
                    rejection_reason="Metaphorical / non-meteorological usage in political or social context.",
                    authority_tier=authority_tier,
                )

        # 3. Political, Crime, Protest, and Civil Non-Weather Check
        for pat in _POLITICAL_CRIME_AND_CIVIL_PATTERNS:
            if pat.search(low) and not has_concrete_met_evidence:
                return RelevanceAssessment(
                    is_relevant=False,
                    incident_nature=IncidentNature.NON_WEATHER_DRILL,
                    primary_category="UNKNOWN",
                    confidence=0.05,
                    severity=1,
                    is_cyclone_rigorous=False,
                    rejection_reason="Political protest, police FIR, election or crime report — zero meteorological hazard content.",
                    authority_tier=authority_tier,
                )

        # 4. Drills & Non-Event Articles Check
        for pat in _DRILL_AND_NON_EVENT_PATTERNS:
            if pat.search(low):
                return RelevanceAssessment(
                    is_relevant=False,
                    incident_nature=IncidentNature.NON_WEATHER_DRILL,
                    primary_category="UNKNOWN",
                    confidence=0.15,
                    severity=1,
                    is_cyclone_rigorous=False,
                    rejection_reason="Drill, simulation, equipment procurement, club or infrastructure analysis — not an active weather hazard.",
                    authority_tier=authority_tier,
                )

        # 5. Historical & Retrospective Check
        for pat in _HISTORICAL_AND_RETROSPECTIVE_PATTERNS:
            if pat.search(low):
                return RelevanceAssessment(
                    is_relevant=False,
                    incident_nature=IncidentNature.HISTORICAL_STUDY,
                    primary_category=claimed_category or "UNKNOWN",
                    confidence=0.30,
                    severity=1,
                    is_cyclone_rigorous=False,
                    rejection_reason="Historical retrospective or educational study of past events — not a current event.",
                    authority_tier=authority_tier,
                )

        # 6. Basic Meteorological Content Verification
        if not _GENUINE_METEOROLOGICAL_TERMS.search(low):
            return RelevanceAssessment(
                is_relevant=False,
                incident_nature=IncidentNature.NON_WEATHER_DRILL,
                primary_category="UNKNOWN",
                confidence=0.05,
                severity=1,
                is_cyclone_rigorous=False,
                rejection_reason="No meteorological keywords or weather phenomena mentioned in text.",
                authority_tier=authority_tier,
            )

        # 7. Forecast & Speculation Gating
        is_speculation = False
        speculation_match = None
        for pat in _FORECAST_AND_SPECULATION_PATTERNS:
            m = pat.search(low)
            if m:
                is_speculation = True
                speculation_match = m.group(0)
                break

        # 8. Cyclone Rigorous Validation & Classification Gating
        is_cyclone_word = bool(re.search(r"\b(cyclone|cyclonic|super\s+cyclone|typhoon|तूफान|తుఫాను|ବାତ୍ୟା|ঘূর্ণিঝড়|புயல்|ചുഴലിക്കാറ്റ്|चक्रीवादळ)\b", low))
        has_official_cyclone_bulletin = any(pat.search(low) for pat in _OFFICIAL_CYCLONE_BULLETIN_PATTERNS)
        
        # Telemetry check for cyclone: wind >= 62 km/h (gale force) or central pressure < 995 hPa
        has_cyclonic_telemetry = False
        if observed_telemetry:
            wind = observed_telemetry.get("wind_speed_kmh") or 0.0
            pressure = observed_telemetry.get("pressure_hpa") or 1013.0
            if wind >= 62.0 or (pressure > 0 and pressure < 995.0):
                has_cyclonic_telemetry = True

        is_cyclone_rigorous = False
        cyclonic_stage: Optional[str] = None
        is_inland_system = False

        if is_cyclone_word or claimed_category == "CYCLONE":
            # Scenario A: Official Bulletin or Direct Scientific Telemetry
            if authority_tier <= SourceAuthorityTier.TIER_2_SCIENTIFIC or has_official_cyclone_bulletin or has_cyclonic_telemetry:
                if has_official_cyclone_bulletin:
                    is_cyclone_rigorous = True
                    cyclonic_stage = CyclonicStage.ACTIVE_CYCLONE.value
                elif has_cyclonic_telemetry:
                    is_cyclone_rigorous = True
                    cyclonic_stage = CyclonicStage.ACTIVE_CYCLONE.value
                elif tracked_parent_system_id:
                    is_cyclone_rigorous = True
                    is_inland_system = True
                    cyclonic_stage = CyclonicStage.POST_LANDFALL_CYCLONE.value
            
            # Scenario B: Speculation / Future Model Output
            if is_speculation:
                return RelevanceAssessment(
                    is_relevant=True,
                    incident_nature=IncidentNature.FORECAST_POTENTIAL,
                    primary_category="RAINFALL" if "rain" in low else ("STRONG_WINDS" if "wind" in low else "UNKNOWN"),
                    confidence=0.50,
                    severity=2,
                    is_cyclone_rigorous=False,
                    cyclonic_stage=CyclonicStage.CYCLONE_WARNING_ADVISORY.value,
                    rejection_reason=f"Speculative / developing forecast ('{speculation_match}'). Gated from active CYCLONE category.",
                    location_specificity="REGIONAL_ONLY" if not has_gps else "EXPLICIT",
                    evidence_signals=["forecast_model_speculation", f"gated_phrase:{speculation_match}"],
                    authority_tier=authority_tier,
                    phenomenon="CYCLONE_ADVISORY",
                    temporal_scope="FORECAST",
                    is_current_observation=False,
                    evidence_basis="FORECAST",
                )

            # Scenario C: Tier 3, 4, 5 Media / Social / Casual Post without Official IMD Cyclone Bulletin
            if not is_cyclone_rigorous and authority_tier >= SourceAuthorityTier.TIER_3_VERIFIED_NEWS:
                # Strictly downgrade to observed physical phenomenon: RAINFALL, STRONG_WINDS, or THUNDERSTORM
                effective_fallback = "THUNDERSTORM" if ("thunder" in low or "lightning" in low or "ఉరుములు" in low) else (
                    "STRONG_WINDS" if ("wind" in low or "gale" in low or "గాలి" in low) else (
                        "RAINFALL" if ("rain" in low or "downpour" in low or "वर्षा" in low or "వర్షం" in low) else "RAINFALL"
                    )
                )
                return RelevanceAssessment(
                    is_relevant=True,
                    incident_nature=IncidentNature.OFFICIAL_WARNING if any(pat.search(low) for pat in _OFFICIAL_WARNING_PATTERNS) else IncidentNature.UNVERIFIED_SIGNAL,
                    primary_category=effective_fallback,
                    confidence=0.49 if authority_tier >= SourceAuthorityTier.TIER_4_REGIONAL_MEDIA else 0.60,
                    severity=2,  # Do NOT assign Sev 3 without verified severity metrics
                    is_cyclone_rigorous=False,
                    cyclonic_stage=CyclonicStage.CYCLONE_CANDIDATE_UNCONFIRMED.value,
                    rejection_reason="Uncorroborated media/social mention of cyclone without official IMD cyclone bulletin or cyclonic telemetry.",
                    location_specificity="REGIONAL_ONLY" if not has_gps else "EXPLICIT",
                    evidence_signals=["downgraded_from_cyclone_to_" + effective_fallback.lower(), "requires_official_imd_bulletin"],
                    authority_tier=authority_tier,
                    phenomenon="CYCLONE_RELATED_ADVISORY" if any(pat.search(low) for pat in _OFFICIAL_WARNING_PATTERNS) else "UNVERIFIED_WEATHER_SIGNAL",
                    temporal_scope="CURRENT",
                    is_current_observation=False if any(pat.search(low) for pat in _OFFICIAL_WARNING_PATTERNS) else True,
                    evidence_basis="NEWS_REPORT" if authority_tier <= SourceAuthorityTier.TIER_4_REGIONAL_MEDIA else "CITIZEN_REPORT",
                )

        # 9. Anomaly & Deficit Detection Patterns
        is_deficit = bool(re.search(
            r"\b(rainfall|rain|monsoon)\s+deficit\b|"
            r"\b(below[\s-]normal|below[\s-]average)\s+(rainfall|rain|monsoon|precipitation)\b|"
            r"\b(rain|rainfall|monsoon)\s+(shortfall|shortage)\b|"
            r"\b(deficient|large\s+deficient)\s+(rainfall|rain|monsoon)\b|"
            r"\bless\s+rainfall\s+than\s+normal\b|"
            r"\bmonsoon\s+deficit\b|"
            r"\b\d+%\s+below\s+normal\b|"
            r"\bmonsoon\s+withdraws.*?\b(?:rain|rainfall)\s+deficit\b|"
            r"\brecord(?:s|ed)?\s+(?:rain|rainfall)\s+deficit\b",
            low
        ))

        is_excess = bool(re.search(
            r"\b(above[\s-]normal|above[\s-]average)\s+(rainfall|rain|monsoon|precipitation)\b|"
            r"\b(rainfall|rain|monsoon)\s+surplus\b|"
            r"\b(excess|large\s+excess)\s+(rainfall|rain|monsoon)\b|"
            r"\b\d+%\s+above\s+normal\b|"
            r"\bsurplus\s+(rainfall|rain|monsoon)\b",
            low
        ))

        is_dry_spell = bool(re.search(
            r"\bdry\s+spell\b|\bprolonged\s+dry\s+spell\b|\bweeks\s+of\s+below[\s-]normal\b",
            low
        ))

        is_no_rain = bool(re.search(
            r"\bno\s+rainfall\s+(?:was\s+)?recorded\b|\bno\s+rain\s+(?:was\s+)?recorded\b|\bzero\s+(?:rainfall|rain)\b|\b0(?:\.0)?\s*mm\s+(?:of\s+)?rain\b|\brain\s*=\s*0\b",
            low
        ))

        # 10. Incident Nature & Provenance Resolution
        phenomenon = "RAINFALL_OBSERVED"
        temporal_scope = "CURRENT"
        is_current_obs = True
        evidence_basis = "CURRENT_OBSERVATION"

        if is_deficit:
            nature = IncidentNature.SEASONAL_ANOMALY
            phenomenon = "RAINFALL_DEFICIT"
            temporal_scope = "SEASONAL" if ("monsoon" in low or "season" in low or "june" in low or "september" in low) else "MONTHLY"
            is_current_obs = False
            evidence_basis = "RAINFALL_ANOMALY"
            conf = 0.88 if authority_tier <= SourceAuthorityTier.TIER_3_VERIFIED_NEWS else 0.75
            sev = 2
        elif is_excess:
            nature = IncidentNature.SEASONAL_ANOMALY
            phenomenon = "RAINFALL_EXCESS"
            temporal_scope = "SEASONAL" if ("monsoon" in low or "season" in low) else "MONTHLY"
            is_current_obs = False
            evidence_basis = "RAINFALL_ANOMALY"
            conf = 0.85
            sev = 2
        elif is_dry_spell:
            nature = IncidentNature.SEASONAL_ANOMALY
            phenomenon = "DRY_SPELL"
            temporal_scope = "WEEKLY"
            is_current_obs = False
            evidence_basis = "RAINFALL_ANOMALY"
            conf = 0.80
            sev = 2
        elif is_no_rain:
            nature = IncidentNature.CURRENT_OBSERVATION
            phenomenon = "NO_RAIN"
            temporal_scope = "CURRENT"
            is_current_obs = True
            evidence_basis = "STATION_TELEMETRY"
            conf = 0.90
            sev = 1
        elif any(pat.search(low) for pat in _OFFICIAL_WARNING_PATTERNS):
            nature = IncidentNature.OFFICIAL_WARNING
            phenomenon = "HEAVY_RAINFALL" if "rain" in low else "WARNING"
            temporal_scope = "CURRENT"
            is_current_obs = False
            evidence_basis = "OFFICIAL_WARNING"
            conf = 0.92 if authority_tier <= SourceAuthorityTier.TIER_2_SCIENTIFIC else 0.80
            sev = 3
        elif any(pat.search(low) for pat in _CURRENT_OBSERVATION_PATTERNS):
            nature = IncidentNature.CURRENT_OBSERVATION
            phenomenon = "HEAVY_RAINFALL" if "heavy" in low or "downpour" in low or "torrential" in low else "RAINFALL_OBSERVED"
            temporal_scope = "CURRENT"
            is_current_obs = True
            evidence_basis = "CURRENT_OBSERVATION"
            conf = 0.88 if authority_tier <= SourceAuthorityTier.TIER_3_VERIFIED_NEWS else 0.70
            sev = 3
        elif is_speculation:
            nature = IncidentNature.FORECAST_POTENTIAL
            phenomenon = "RAINFALL_OBSERVED"
            temporal_scope = "CURRENT"
            is_current_obs = False
            evidence_basis = "FORECAST"
            conf = 0.65
            sev = 2
        elif authority_tier == SourceAuthorityTier.TIER_5_CITIZEN_SOCIAL:
            nature = IncidentNature.UNVERIFIED_SIGNAL
            phenomenon = "RAINFALL_OBSERVED"
            temporal_scope = "CURRENT"
            is_current_obs = True
            evidence_basis = "CITIZEN_REPORT"
            conf = 0.50
            sev = 2
        else:
            nature = IncidentNature.CURRENT_OBSERVATION
            phenomenon = "RAINFALL_OBSERVED"
            temporal_scope = "CURRENT"
            is_current_obs = True
            evidence_basis = "NEWS_REPORT"
            conf = 0.75
            sev = 2

        # 11. Semantic Category Resolution
        if is_cyclone_rigorous:
            effective_category = "CYCLONE"
            phenomenon = cyclonic_stage or "CYCLONIC_STORM"
        elif ("heavy rain" in low or "downpour" in low or "torrential" in low or "lashes" in low) and not ("river" in low or "breach" in low or "inundat" in low):
            effective_category = "RAINFALL"
            phenomenon = "EXTREME_RAINFALL" if ("cloudburst" in low or "torrential" in low or "extremely heavy" in low) else "HEAVY_RAINFALL"
        elif "flood" in low or "waterlog" in low or "inundat" in low:
            effective_category = "FLOODING"
            phenomenon = "URBAN_FLOOD" if "urban" in low or "street" in low else ("FLASH_FLOOD" if "flash" in low else "FLOODING")
        elif "thunder" in low or "lightning" in low:
            effective_category = "THUNDERSTORM"
            phenomenon = "SEVERE_THUNDERSTORM" if "severe" in low or "heavy" in low else "THUNDERSTORM_ACTIVE"
        elif "heat" in low or "temperature" in low or "loo" in low:
            effective_category = "HEATWAVE"
            phenomenon = "HEATWAVE_SEVERE" if "severe" in low or "extreme" in low else "HEATWAVE_MODERATE"
        elif "fog" in low or "visibility" in low:
            effective_category = "FOG"
            phenomenon = "DENSE_FOG" if "dense" in low or "zero" in low else "SHALLOW_FOG"
        elif "dust" in low:
            effective_category = "DUST_STORM"
            phenomenon = "DUST_STORM_SEVERE"
        elif "landslide" in low or "mudslide" in low:
            effective_category = "LANDSLIDE"
        elif "drought" in low:
            effective_category = "DROUGHT"
        elif "cold" in low or "chill" in low or "frost" in low:
            effective_category = "COLDWAVE"
        elif "rain" in low or "precipitation" in low or "downpour" in low or "monsoon" in low:
            effective_category = "RAINFALL"
            if not is_deficit and not is_excess and not is_dry_spell and not is_no_rain:
                if "cloudburst" in low or "torrential" in low or "extremely heavy" in low:
                    phenomenon = "EXTREME_RAINFALL"
                elif "heavy" in low or "lashes" in low or "downpour" in low:
                    phenomenon = "HEAVY_RAINFALL"
                else:
                    phenomenon = "RAINFALL_OBSERVED"
        elif "wind" in low or "gale" in low or "squall" in low:
            effective_category = "STRONG_WINDS"
            phenomenon = "GALE_WINDS" if "gale" in low else "SQUALL"
        else:
            effective_category = "RAINFALL" if claimed_category == "RAINFALL" else "UNKNOWN"

        return RelevanceAssessment(
            is_relevant=True,
            incident_nature=nature,
            primary_category=effective_category,
            confidence=conf,
            severity=sev,
            is_cyclone_rigorous=is_cyclone_rigorous,
            cyclonic_stage=cyclonic_stage,
            lineage_system_id=tracked_parent_system_id,
            is_inland_system=is_inland_system,
            location_specificity="EXPLICIT" if has_gps else "REGIONAL_ONLY",
            authority_tier=authority_tier,
            evidence_signals=[f"nature:{nature.value}", f"phenomenon:{phenomenon}", f"tier:{authority_tier.name}"],
            phenomenon=phenomenon,
            temporal_scope=temporal_scope,
            is_current_observation=is_current_obs,
            evidence_basis=evidence_basis,
        )
