"""
Unit & Integration Tests for SkyPulse Groq LLM Weather Intelligence
Tests structured JSON output, schema validation, zero GPS hallucination,
rate-limit resilience, retry backoff, deterministic fallback, telemetry, and pipeline integration.
"""

import os
import json
import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import Response, Request, TimeoutException
from sqlalchemy import select

from ai.groq_provider import (
    GroqProvider,
    GroqWeatherClassification,
    ALLOWED_SIH_CATEGORIES,
    groq_provider,
)
from ai.base_provider import ClassificationResult, EntityExtractionResult
from ai.event_classifier import EventClassifier
from ai.nlp_extractor import NLPExtractor
from app.core.config import settings
from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from connectors.schema import CanonicalRawEvent
from app.services.unified_ingestion_service import UnifiedIngestionPipelineService


# ==============================================================================
# 1. Configuration & Unconfigured Fallback Tests
# ==============================================================================

def test_1_groq_configuration_defaults():
    """Verifies default Groq configuration values and unconfigured state when no API key is provided."""
    provider = GroqProvider(api_key=None)
    assert provider.name == "GroqProvider"
    assert provider.model == "llama-3.3-70b-versatile"
    assert provider.timeout == 15.0
    assert provider.max_retries == 2
    assert provider.is_configured is False
    assert provider.status == "NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_2_groq_unconfigured_fallback_behavior():
    """Verifies that an unconfigured Groq provider automatically delegates to deterministic fallback AI."""
    provider = GroqProvider(api_key="")
    assert provider.is_configured is False

    result = await provider.classify_event("Heavy thunderstorm and lightning in Cuttack, Odisha.")
    assert result is not None
    assert result.category in ("THUNDERSTORM", "RAINFALL")
    assert result.confidence >= 0.5
    # Should flag that fallback was used
    assert result.fallback_used is True or result.method in ("fallback_heuristic", "rule_based")


# ==============================================================================
# 2. Structured JSON Output & Category Validation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_3_groq_successful_structured_classification_mock():
    """
    Tests successful Groq inference using structured JSON mode mock.
    Verifies valid SIH category mapping, severity bounds, telemetry update, and no GPS hallucination.
    """
    mock_payload = {
        "id": "chatcmpl-test-groq-01",
        "object": "chat.completion",
        "created": 1710000000,
        "model": "llama-3.3-70b-versatile",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "is_weather_related": True,
                        "category": "RAIN",
                        "severity": 3,
                        "confidence": 0.89,
                        "location": {
                            "city": "Bhubaneswar",
                            "district": "Khordha",
                            "state": "Odisha"
                        },
                        "measurements": {
                            "rainfall_mm": 72.5,
                            "temperature_c": None,
                            "wind_speed_kmh": 40.0,
                            "visibility_km": 2.0,
                            "flood_depth_ft": None
                        },
                        "reasoning": "Continuous intense rainfall reported causing road inundation.",
                        "evidence_signals": ["rainfall_mm:72.5", "inundation"]
                    }),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 85,
            "total_tokens": 205,
        },
    }

    mock_resp = Response(
        status_code=200,
        content=json.dumps(mock_payload).encode("utf-8"),
        request=Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )

    provider = GroqProvider(api_key="gsk_mock_valid_key_for_testing_12345")
    assert provider.is_configured is True

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        result = await provider.classify_event(
            "Continuous torrential rain in Bhubaneswar with 72.5mm recorded.",
            metadata={"location_name": "Bhubaneswar, Odisha"}
        )

        assert result is not None
        assert result.category == "RAINFALL"  # Normalized from RAIN
        assert result.confidence == 0.89
        assert result.severity == 3
        assert result.method == "GROQ"
        assert result.model == "llama-3.3-70b-versatile"
        assert result.fallback_used is False

        # Verify telemetry recorded
        telemetry = provider.telemetry.to_dict()
        assert telemetry["request_count"] == 1
        assert telemetry["success_count"] == 1
        assert telemetry["failure_count"] == 0
        assert telemetry["total_prompt_tokens"] == 120
        assert telemetry["total_completion_tokens"] == 85


@pytest.mark.asyncio
async def test_4_groq_category_membership_and_bounds():
    """Verifies that invalid categories from LLM default to UNKNOWN and severity is clamped to [1, 5]."""
    test_data = {
        "is_weather_related": True,
        "category": "ALIEN_INVASION",  # Not an SIH category
        "severity": 10,                # Out of bounds
        "confidence": 1.5,             # Out of bounds
        "location": {"city": "Delhi"},
        "measurements": {},
        "reasoning": "Strange storm",
    }

    parsed = GroqWeatherClassification.model_validate(test_data)
    assert parsed.category == "UNKNOWN"
    assert parsed.severity == 5  # Clamped to max le=5
    assert parsed.confidence == 1.0  # Clamped to max le=1.0


# ==============================================================================
# 3. Fault Resilience, Rate Limiting, & Retries
# ==============================================================================

@pytest.mark.asyncio
async def test_5_groq_rate_limiting_429_backoff_and_fallback():
    """
    Verifies that HTTP 429 rate-limit triggers exponential backoff retries and
    falls back cleanly to FallbackAIProvider without crashing.
    """
    mock_429 = Response(
        status_code=429,
        content=b'{"error": {"message": "Rate limit reached", "type": "tokens"}}',
        request=Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )

    provider = GroqProvider(api_key="gsk_mock_valid_key_for_testing_12345")
    provider.max_retries = 1  # Fast test

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_post.return_value = mock_429

        result = await provider.classify_event("Heavy flood in Patna, Bihar.")

        assert result is not None
        assert result.category == "FLOODING"
        assert result.fallback_used is True
        assert provider.telemetry.rate_limit_count >= 1
        assert provider.telemetry.fallback_count >= 1
        assert mock_sleep.called


@pytest.mark.asyncio
async def test_6_groq_timeout_and_network_error_resilience():
    """Verifies that timeout exceptions do not crash the pipeline and trigger fallback."""
    provider = GroqProvider(api_key="gsk_mock_valid_key_for_testing_12345")
    provider.max_retries = 1

    with patch("httpx.AsyncClient.post", side_effect=TimeoutException("Connection timed out")), \
         patch("asyncio.sleep", new_callable=AsyncMock):

        result = await provider.classify_event("Severe heatwave in Jaipur with 46C temperature.")

        assert result is not None
        assert result.category == "HEATWAVE"
        assert result.fallback_used is True
        assert provider.telemetry.failure_count >= 1
        assert provider.telemetry.last_error_code == "TIMEOUT"


@pytest.mark.asyncio
async def test_7_groq_in_memory_deduplication_cache():
    """
    Verifies that repeated calls with the exact same text hit the in-memory
    deduplication cache and avoid redundant network calls.
    """
    provider = GroqProvider(api_key="gsk_mock_valid_key_for_testing_12345")

    mock_payload = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "is_weather_related": True,
                    "category": "FOG",
                    "severity": 2,
                    "confidence": 0.85,
                    "location": {"city": "Amritsar"},
                    "measurements": {"visibility_km": 0.05},
                    "reasoning": "Dense fog visibility 50m",
                })
            }
        }],
        "usage": {"prompt_tokens": 50, "completion_tokens": 30},
    }
    mock_resp = Response(
        status_code=200,
        content=json.dumps(mock_payload).encode("utf-8"),
        request=Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        # Call 1
        res1 = await provider.classify_event("Dense fog over Amritsar highway reducing visibility.")
        assert res1.category == "FOG"
        assert mock_post.call_count == 1

        # Call 2 with identical text
        res2 = await provider.classify_event("Dense fog over Amritsar highway reducing visibility.")
        assert res2.category == "FOG"
        # call_count should still be 1 because cached!
        assert mock_post.call_count == 1


# ==============================================================================
# 4. Zero GPS Hallucination & Entity Extraction Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_8_groq_entity_extraction_and_zero_gps_fabrication():
    """
    Verifies that entity extraction parses measurements, but lat/lon are strictly
    sourced from validated metadata and never invented by the LLM.
    """
    mock_payload = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "is_weather_related": True,
                    "category": "STRONG_WINDS",
                    "severity": 3,
                    "confidence": 0.90,
                    "location": {
                        "city": "Puri",
                        "district": "Puri",
                        "state": "Odisha"
                    },
                    "measurements": {
                        "rainfall_mm": 15.0,
                        "temperature_c": None,
                        "wind_speed_kmh": 68.0,
                        "visibility_km": None,
                        "flood_depth_ft": None
                    },
                    "reasoning": "Squally winds 68 km/h along Puri beach",
                })
            }
        }],
        "usage": {"prompt_tokens": 60, "completion_tokens": 40},
    }
    mock_resp = Response(
        status_code=200,
        content=json.dumps(mock_payload).encode("utf-8"),
        request=Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )

    provider = GroqProvider(api_key="gsk_mock_valid_key_for_testing_12345")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        # Case A: No GPS provided in metadata
        res_no_gps = await provider.extract_entities(
            "Gale winds up to 68 km/h blowing across Puri coastline.",
            metadata={"location_name": "Puri, Odisha"}
        )
        assert res_no_gps.resolved_city == "Puri"
        assert res_no_gps.resolved_lat is None
        assert res_no_gps.resolved_lon is None
        assert len(res_no_gps.weather_attributes) >= 1
        assert res_no_gps.weather_attributes[0].name == "wind_speed_kmh" or any(a.name == "wind_speed_kmh" for a in res_no_gps.weather_attributes)

        # Case B: Real GPS provided in metadata
        res_with_gps = await provider.extract_entities(
            "Gale winds up to 68 km/h blowing across Puri coastline.",
            metadata={"latitude": 19.8135, "longitude": 85.8312}
        )
        assert res_with_gps.resolved_lat == 19.8135
        assert res_with_gps.resolved_lon == 85.8312


# ==============================================================================
# 5. Pipeline Integration & API Endpoint Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_9_groq_in_unified_weather_pipeline(db_session):
    """
    Verifies end-to-end integration:
    CanonicalRawEvent -> UnifiedIngestionPipeline -> GroqProvider -> WeatherReport -> WeatherEvent -> DWEG
    """
    mock_payload = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "is_weather_related": True,
                    "category": "DUST_STORM",
                    "severity": 3,
                    "confidence": 0.88,
                    "location": {"city": "Bikaner", "state": "Rajasthan"},
                    "measurements": {"wind_speed_kmh": 55.0, "visibility_km": 0.5},
                    "reasoning": "Massive dust storm in Bikaner reducing visibility.",
                })
            }
        }],
        "usage": {"prompt_tokens": 80, "completion_tokens": 50},
    }
    mock_resp = Response(
        status_code=200,
        content=json.dumps(mock_payload).encode("utf-8"),
        request=Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )

    test_groq = GroqProvider(api_key="gsk_mock_valid_key_for_testing_12345")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        classifier = EventClassifier(provider=test_groq)
        extractor = NLPExtractor(provider=test_groq)

        pipeline = UnifiedIngestionPipelineService()
        pipeline._classifier = classifier
        pipeline._nlp_extractor = extractor

        raw_event = CanonicalRawEvent(
            source_id="00000000-0000-0000-0000-000000000001",
            source_type="SOCIAL_MEDIA",
            external_id="GROQ-PIPELINE-TEST-01",
            text="Blinding dust storm hitting Bikaner, highway traffic halted! #DustStorm",
            latitude=28.0229,
            longitude=73.3119,
            city="Bikaner",
            state="Rajasthan",
            suggested_category="DUST_STORM",
            severity=3,
        )

        res = await pipeline.ingest_canonical_event(raw_event, db=db_session)
        assert res.status == "SUCCESS"
        assert res.category == "DUST_STORM"
        assert res.canonical_event_id is not None

        # Verify WeatherReport classification_method in database
        report = await db_session.scalar(
            select(WeatherReport).where(WeatherReport.id == uuid.UUID(res.report_id))
        )
        assert report is not None
        assert report.classification_method == "GROQ"
        assert report.primary_category == "DUST_STORM"


@pytest.mark.asyncio
async def test_10_ai_status_and_telemetry_endpoints(client):
    """Verifies that the /api/v1/ai/status and /api/v1/ai/telemetry endpoints work cleanly without secrets."""
    resp = await client.get("/api/v1/ai/status")
    assert resp.status_code == 200
    data = resp.json()

    assert data["provider"] == "groq"
    assert "configured" in data
    assert "model" in data
    assert "status" in data
    assert data["fallback_enabled"] is True
    assert "telemetry" in data

    # Security guarantee: no API keys or secrets in response
    resp_text = resp.text
    assert "gsk_" not in resp_text
    assert "api_key" not in data
    assert "GROQ_API_KEY" not in resp_text


# ==============================================================================
# 6. Real Live Smoke Test (Runs Only When Local GROQ_API_KEY Is Present)
# ==============================================================================

@pytest.mark.asyncio
async def test_11_real_groq_live_smoke_test():
    """
    Live Smoke Test against Groq's official API endpoint.
    Automatically executes when a valid GROQ_API_KEY is detected in environment/.env;
    otherwise skips cleanly.
    """
    real_key = os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)
    if not real_key or len(real_key.strip()) < 10 or "mock" in real_key.lower():
        pytest.skip("GROQ_API_KEY not configured locally in environment/.env for live smoke test")

    provider = GroqProvider(api_key=real_key)
    assert provider.is_configured is True

    test_input = "Heavy rainfall reported in Bhubaneswar with severe waterlogging near railway station."
    result = await provider.classify_event(test_input)

    assert result is not None
    assert result.category in ALLOWED_SIH_CATEGORIES.values()
    assert result.method == "GROQ"
    assert result.model == provider.model
    assert result.confidence >= 0.5
    assert provider.telemetry.success_count >= 1
    assert provider.telemetry.last_latency_ms > 0
