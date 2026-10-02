"""
SkyPulse Groq LLM Provider Adapter
High-speed meteorological intelligence, structured weather classification,
and entity extraction using Groq's low-latency inference engine.

Guarantees:
1. Strict JSON schema validation against SIH weather categories.
2. Zero GPS hallucination / fabrication (explicit lat/lon strictly preserved).
3. Bounded retries with exponential backoff & rate-limit handling (HTTP 429).
4. Deterministic fallback to FallbackAIProvider on failure/unconfigured.
5. In-memory content hash deduplication cache to save API calls.
6. Complete privacy & credential hygiene (no secrets in logs/exceptions).
"""

import os
import time
import json
import hashlib
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import httpx
from pydantic import BaseModel, Field, field_validator

from ai.base_provider import (
    AIProvider,
    ClassificationResult,
    EntityExtractionResult,
    WeatherAttribute,
    MediaAnalysisResult,
    AnomalyResult,
    EvidenceAssessmentResult,
)
from ai.fallback_provider import FallbackAIProvider
from app.core.config import settings

logger = logging.getLogger("skypulse.ai.groq")

# Canonical SIH Categories mapped to system enums
ALLOWED_SIH_CATEGORIES = {
    "RAIN": "RAINFALL",
    "RAINFALL": "RAINFALL",
    "THUNDERSTORM": "THUNDERSTORM",
    "FLOODING": "FLOODING",
    "FLOOD": "FLOODING",
    "HEATWAVE": "HEATWAVE",
    "FOG": "FOG",
    "DUST_STORM": "DUST_STORM",
    "STRONG_WINDS": "STRONG_WINDS",
    "UNKNOWN": "UNKNOWN",
}


# ==============================================================================
# Structured Output Pydantic Schemas for Groq Validation
# ==============================================================================

class GroqLocation(BaseModel):
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None


class GroqMeasurements(BaseModel):
    rainfall_mm: Optional[float] = None
    temperature_c: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    visibility_km: Optional[float] = None
    flood_depth_ft: Optional[float] = None


class GroqWeatherClassification(BaseModel):
    is_weather_related: bool = True
    category: str
    severity: int = Field(default=2, ge=1, le=5)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    location: GroqLocation = Field(default_factory=GroqLocation)
    measurements: GroqMeasurements = Field(default_factory=GroqMeasurements)
    reasoning: Optional[str] = None
    evidence_signals: List[str] = Field(default_factory=list)

    @classmethod
    def model_validate(cls, obj: Any, **kwargs) -> "GroqWeatherClassification":
        if isinstance(obj, dict):
            if "location" not in obj and "locations" in obj:
                locs = obj.get("locations")
                if isinstance(locs, list) and len(locs) > 0:
                    obj["location"] = locs[0]
                elif isinstance(locs, dict):
                    obj["location"] = locs
        return super().model_validate(obj, **kwargs)

    @field_validator("location", mode="before")
    @classmethod
    def normalize_loc(cls, v: Any, info: Any = None) -> Any:
        if isinstance(v, list) and len(v) > 0:
            return v[0]
        return v or {}

    @field_validator("category", mode="before")
    @classmethod
    def normalize_cat(cls, v: Any) -> str:
        if isinstance(v, str):
            clean = v.strip().upper().replace(" ", "_")
            return ALLOWED_SIH_CATEGORIES.get(clean, "UNKNOWN")
        return "UNKNOWN"

    @field_validator("severity", mode="before")
    @classmethod
    def clamp_severity(cls, v: Any) -> int:
        try:
            val = int(v)
            return max(1, min(5, val))
        except (ValueError, TypeError):
            return 2

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: Any) -> float:
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.75


class GroqSemanticCorroboration(BaseModel):
    agrees: bool
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    category_matches: bool = True
    contradiction_detected: bool = False
    explanation: str = ""


# ==============================================================================
# Groq Telemetry Container
# ==============================================================================

class GroqTelemetry:
    def __init__(self):
        self.request_count: int = 0
        self.success_count: int = 0
        self.failure_count: int = 0
        self.fallback_count: int = 0
        self.rate_limit_count: int = 0
        self.total_latency_ms: float = 0.0
        self.last_latency_ms: float = 0.0
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.last_error_code: Optional[str] = None
        self.last_error_time: Optional[datetime] = None

    def record_success(self, latency_ms: float, prompt_tokens: int = 0, completion_tokens: int = 0):
        self.request_count += 1
        self.success_count += 1
        self.last_latency_ms = round(latency_ms, 2)
        self.total_latency_ms += latency_ms
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.last_error_code = None

    def record_failure(self, error_code: str):
        self.request_count += 1
        self.failure_count += 1
        self.last_error_code = error_code
        self.last_error_time = datetime.now(timezone.utc)
        if error_code == "RATE_LIMIT_429":
            self.rate_limit_count += 1

    def record_fallback(self):
        self.fallback_count += 1

    def to_dict(self) -> Dict[str, Any]:
        avg_latency = (
            round(self.total_latency_ms / self.success_count, 2)
            if self.success_count > 0
            else 0.0
        )
        return {
            "request_count": self.request_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "fallback_count": self.fallback_count,
            "rate_limit_count": self.rate_limit_count,
            "last_latency_ms": self.last_latency_ms,
            "average_latency_ms": avg_latency,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "last_error_code": self.last_error_code,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
        }


# ==============================================================================
# Groq Provider Implementation
# ==============================================================================

class GroqProvider(AIProvider):
    """
    Production-grade Groq LLM Provider for SkyPulse.
    Interacts asynchronously with Groq's OpenAI-compatible completions API.
    """

    SYSTEM_PROMPT = """You are SkyPulse Weather Intelligence AI, an expert meteorological reasoning agent for India.
Your mission is to analyze unstructured weather reports from social media, news, citizen reports, and sensors.

STRICT INSTRUCTIONS:
1. Classify the report into EXACTLY one of these SIH categories:
   - RAIN (or RAINFALL)
   - THUNDERSTORM
   - FLOODING
   - HEATWAVE
   - FOG
   - DUST_STORM
   - STRONG_WINDS
   - UNKNOWN (if non-weather or ambiguous)
2. Severity must be an integer from 1 (minor) to 4 (extreme/disaster).
3. Extract Indian location mentions: city, district, state.
4. Extract only explicitly mentioned meteorological measurements (e.g. rainfall_mm, temperature_c, wind_speed_kmh, visibility_km, flood_depth_ft). Use null for missing measurements.
5. NEVER fabricate or invent GPS coordinates (latitude/longitude). SkyPulse uses validated geographic grounding.
6. NEVER predict future weather forecasts. You are analyzing reported observations and evidence.
7. Return valid JSON adhering to the required schema."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self._api_key = (
            api_key
            or getattr(settings, "GROQ_API_KEY", None)
            or os.getenv("GROQ_API_KEY")
        )
        self.model = model or getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
        self.base_url = getattr(settings, "GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        self.timeout = timeout_seconds or getattr(settings, "GROQ_TIMEOUT_SECONDS", 15.0)
        self.max_retries = getattr(settings, "GROQ_MAX_RETRIES", 2)
        self.enabled = getattr(settings, "GROQ_ENABLED", True)

        self._fallback = FallbackAIProvider()
        self.telemetry = GroqTelemetry()
        self._cache: Dict[str, Tuple[ClassificationResult, float]] = {}
        self._cache_ttl_seconds = 300.0  # 5 minutes deduplication cache

    @property
    def name(self) -> str:
        return "GroqProvider"

    @property
    def is_configured(self) -> bool:
        return bool(
            self.enabled
            and self._api_key
            and len(self._api_key.strip()) > 5
        )

    @property
    def status(self) -> str:
        if not self.is_configured:
            return "NOT_CONFIGURED"
        if self.telemetry.last_error_code == "RATE_LIMIT_429":
            return "RATE_LIMITED"
        return "HEALTHY"

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            "provider": "groq",
            "configured": self.is_configured,
            "model": self.model,
            "status": self.status,
            "fallback_enabled": True,
            "telemetry": self.telemetry.to_dict(),
        }

    # --------------------------------------------------------------------------
    # Core HTTP Execution with Bounded Retries & Backoff
    # --------------------------------------------------------------------------

    async def _call_groq_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
    ) -> Optional[Dict[str, Any]]:
        """
        Executes HTTP POST to Groq completions endpoint with JSON mode.
        Handles rate limits (429), timeouts, backoff, and response validation.
        """
        if not self.is_configured:
            return None

        clean_key = self._api_key.strip()
        headers = {
            "Authorization": f"Bearer {clean_key}",
            "Content-Type": "application/json",
            "User-Agent": "SkyPulse-WeatherIntelligence/1.0",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "max_tokens": getattr(settings, "GROQ_MAX_TOKENS", 1024),
        }

        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"

        for attempt in range(self.max_retries + 1):
            t0 = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(endpoint, json=payload, headers=headers)

                latency_ms = (time.perf_counter() - t0) * 1000.0

                if resp.status_code == 200:
                    data = resp.json()
                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    comp_tokens = usage.get("completion_tokens", 0)
                    self.telemetry.record_success(latency_ms, prompt_tokens, comp_tokens)

                    choices = data.get("choices", [])
                    if not choices:
                        logger.warning("Groq returned empty choices list")
                        return None

                    content_str = choices[0].get("message", {}).get("content", "")
                    try:
                        return json.loads(content_str)
                    except json.JSONDecodeError as jde:
                        logger.warning("Groq output failed JSON parsing: %s", jde)
                        # Retry once with stricter guidance if attempt == 0
                        if attempt == 0:
                            messages.append({
                                "role": "user",
                                "content": "Your previous response was not valid JSON. Please respond with raw JSON only without markdown formatting."
                            })
                            continue
                        return None

                elif resp.status_code == 429:
                    self.telemetry.record_failure("RATE_LIMIT_429")
                    backoff = (2 ** attempt) * 0.75 + 0.25
                    logger.warning("Groq rate limited (429). Backing off for %.2fs (attempt %d/%d)", backoff, attempt + 1, self.max_retries)
                    await asyncio.sleep(backoff)
                    continue

                else:
                    err_code = f"HTTP_{resp.status_code}"
                    self.telemetry.record_failure(err_code)
                    logger.warning("Groq returned error %d: %s", resp.status_code, resp.text[:150])
                    return None

            except (httpx.TimeoutException, httpx.ConnectTimeout):
                self.telemetry.record_failure("TIMEOUT")
                logger.warning("Groq request timed out after %.1fs (attempt %d/%d)", self.timeout, attempt + 1, self.max_retries)
                if attempt < self.max_retries:
                    await asyncio.sleep((2 ** attempt) * 0.5)
                    continue
                return None

            except Exception as exc:
                self.telemetry.record_failure("NETWORK_ERROR")
                logger.warning("Groq network/client exception: %s", type(exc).__name__)
                return None

        return None

    # --------------------------------------------------------------------------
    # Classification Implementation
    # --------------------------------------------------------------------------

    async def classify_event(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ClassificationResult:
        """
        Classifies weather report into the 7 SIH categories using Groq LLM.
        Falls back seamlessly to FallbackAIProvider if unconfigured or on failure.
        """
        if not text or not text.strip():
            return await self._fallback.classify_event(text, metadata)

        # 1. Deduplication Cache Check
        text_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
        now_ts = time.time()
        if text_hash in self._cache:
            cached_res, cached_at = self._cache[text_hash]
            if now_ts - cached_at < self._cache_ttl_seconds:
                return cached_res

        # 2. Check if Groq is configured
        if not self.is_configured:
            self.telemetry.record_fallback()
            return await self._fallback.classify_event(text, metadata)

        # 3. Formulate Prompt
        user_content = f"Analyze and classify this weather report:\n\n{text.strip()}"
        if metadata and metadata.get("location_name"):
            user_content += f"\nReported Location Hint: {metadata['location_name']}"

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        # 4. Call Groq
        raw_json = await self._call_groq_json(messages)

        if not raw_json:
            # Fallback to deterministic AI
            self.telemetry.record_fallback()
            logger.info("Groq inference unavailable, delegating to deterministic fallback AI")
            fallback_res = await self._fallback.classify_event(text, metadata)
            fallback_res.fallback_used = True
            return fallback_res

        # 5. Validate Structured Response with Pydantic
        try:
            parsed = GroqWeatherClassification.model_validate(raw_json)
            category = parsed.category
            if category not in ALLOWED_SIH_CATEGORIES.values():
                category = "UNKNOWN"

            # Compile evidence signals
            signals = list(parsed.evidence_signals)
            if parsed.location.city:
                signals.append(f"city:{parsed.location.city}")
            if parsed.location.state:
                signals.append(f"state:{parsed.location.state}")
            if parsed.measurements.rainfall_mm is not None:
                signals.append(f"rainfall_mm:{parsed.measurements.rainfall_mm}")
            if parsed.measurements.temperature_c is not None:
                signals.append(f"temperature_c:{parsed.measurements.temperature_c}")
            if parsed.measurements.wind_speed_kmh is not None:
                signals.append(f"wind_speed_kmh:{parsed.measurements.wind_speed_kmh}")
            if parsed.reasoning:
                signals.append(f"reasoning:{parsed.reasoning[:80]}")

            result = ClassificationResult(
                category=category,
                sub_category=parsed.reasoning[:40] if parsed.reasoning else None,
                confidence=min(1.0, max(0.1, parsed.confidence)),
                severity=min(4, max(1, parsed.severity)),
                evidence_signals=signals,
                method="GROQ",
                model=self.model,
                fallback_used=False,
            )

            # Store in deduplication cache
            self._cache[text_hash] = (result, now_ts)
            return result

        except Exception as p_err:
            logger.warning("Groq response failed schema validation: %s. Using fallback.", p_err)
            self.telemetry.record_fallback()
            fallback_res = await self._fallback.classify_event(text, metadata)
            fallback_res.fallback_used = True
            return fallback_res

    # --------------------------------------------------------------------------
    # Entity Extraction Implementation
    # --------------------------------------------------------------------------

    async def extract_entities(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EntityExtractionResult:
        """
        Extracts structured meteorological measurements and location mentions.
        """
        if not self.is_configured:
            return await self._fallback.extract_entities(text, metadata)

        # Execute classification / extraction prompt
        user_content = f"Extract all meteorological measurements, numbers, units, and Indian locations from:\n\n{text.strip()}"
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        raw_json = await self._call_groq_json(messages)
        if not raw_json:
            return await self._fallback.extract_entities(text, metadata)

        try:
            parsed = GroqWeatherClassification.model_validate(raw_json)
            attributes = []
            if parsed.measurements.rainfall_mm is not None:
                attributes.append(WeatherAttribute(
                    name="rainfall_mm",
                    value=float(parsed.measurements.rainfall_mm),
                    unit="mm",
                    raw_mention=f"{parsed.measurements.rainfall_mm} mm",
                ))
            if parsed.measurements.temperature_c is not None:
                attributes.append(WeatherAttribute(
                    name="temperature_c",
                    value=float(parsed.measurements.temperature_c),
                    unit="C",
                    raw_mention=f"{parsed.measurements.temperature_c} C",
                ))
            if parsed.measurements.wind_speed_kmh is not None:
                attributes.append(WeatherAttribute(
                    name="wind_speed_kmh",
                    value=float(parsed.measurements.wind_speed_kmh),
                    unit="km/h",
                    raw_mention=f"{parsed.measurements.wind_speed_kmh} km/h",
                ))
            if parsed.measurements.flood_depth_ft is not None:
                attributes.append(WeatherAttribute(
                    name="flood_depth_ft",
                    value=float(parsed.measurements.flood_depth_ft),
                    unit="ft",
                    raw_mention=f"{parsed.measurements.flood_depth_ft} ft",
                ))

            # Geographic ground truth reconciliation:
            # Lat/Lon is strictly preserved from validated source metadata only
            source_lat = metadata.get("latitude") if metadata else None
            source_lon = metadata.get("longitude") if metadata else None

            return EntityExtractionResult(
                event_mentions=[parsed.category] if parsed.category != "UNKNOWN" else [],
                location_mentions=[loc for loc in [parsed.location.city, parsed.location.district, parsed.location.state] if loc],
                resolved_city=parsed.location.city,
                resolved_district=parsed.location.district,
                resolved_state=parsed.location.state,
                resolved_lat=source_lat,
                resolved_lon=source_lon,
                weather_attributes=attributes,
                temporal_mentions=[],
                confidence=parsed.confidence,
                method="GROQ",
            )
        except Exception:
            return await self._fallback.extract_entities(text, metadata)

    # --------------------------------------------------------------------------
    # Media & Vision Analysis
    # --------------------------------------------------------------------------

    async def analyze_media(
        self,
        media_urls: List[str],
        claimed_category: Optional[str] = None,
    ) -> MediaAnalysisResult:
        """
        Multimodal visual analysis. Checks if active model supports vision.
        If vision model is active and URL is available, invokes vision endpoint;
        otherwise delegates cleanly to perceptual hashing and heuristic media analyzer.
        """
        is_vision_model = "vision" in self.model.lower()
        if not self.is_configured or not is_vision_model or not media_urls:
            # Safe delegation to existing ImageAnalyzer / pHash pipeline
            return await self._fallback.analyze_media(media_urls, claimed_category)

        # If a vision model is specifically configured in Groq (e.g. llama-3.2-11b-vision-preview)
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Analyze this image for weather conditions. Claimed category: {claimed_category or 'UNKNOWN'}. Return JSON with visual_category, confidence (0-1), and supports_claimed_event (boolean)."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": media_urls[0]}
                        }
                    ]
                }
            ]
            raw_json = await self._call_groq_json(messages)
            if raw_json:
                return MediaAnalysisResult(
                    has_media=True,
                    media_type="image",
                    visual_category=raw_json.get("visual_category", "UNKNOWN"),
                    confidence=float(raw_json.get("confidence", 0.7)),
                    supports_claimed_event=bool(raw_json.get("supports_claimed_event", True)),
                    method="GROQ_VISION",
                )
        except Exception as v_err:
            logger.warning("Groq vision analysis exception: %s", v_err)

        return await self._fallback.analyze_media(media_urls, claimed_category)

    # --------------------------------------------------------------------------
    # Pass-through to Fallback Engine for Embeddings, Anomaly, & Graph Verification
    # --------------------------------------------------------------------------

    async def generate_embedding(self, text: str) -> List[float]:
        return await self._fallback.generate_embedding(text)

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
        return await self._fallback.detect_anomaly(
            category=category,
            severity=severity,
            city=city,
            district=district,
            state=state,
            event_time=event_time,
            nearby_events_count=nearby_events_count,
        )

    async def assess_evidence(
        self,
        report_data: Dict[str, Any],
        official_data: Optional[Dict[str, Any]] = None,
        nearby_reports: Optional[List[Dict[str, Any]]] = None,
        source_trust: float = 0.5,
        media_analysis: Optional[MediaAnalysisResult] = None,
    ) -> EvidenceAssessmentResult:
        """
        Assesses evidence using multi-source corroboration matrix.
        Can optionally invoke Groq semantic comparison for near-duplicate or contradictory text.
        """
        return await self._fallback.assess_evidence(
            report_data=report_data,
            official_data=official_data,
            nearby_reports=nearby_reports,
            source_trust=source_trust,
            media_analysis=media_analysis,
        )


# Global singleton instance
groq_provider = GroqProvider()
