"""
SkyPulse AI Provider Status & Telemetry API
Exposes health, configured models, fallback status, and inference telemetry.
Guarantees zero credential leakage.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ai.groq_provider import groq_provider
from ai.event_classifier import EventClassifier
from ai.base_provider import ClassificationResult
from app.core.config import settings

logger = logging.getLogger("skypulse.api.ai")

router = APIRouter(prefix="/ai", tags=["AI & Weather Intelligence"])


class AIStatusResponse(BaseModel):
    provider: str
    configured: bool
    model: str
    status: str  # HEALTHY, NOT_CONFIGURED, RATE_LIMITED, DEGRADED
    fallback_enabled: bool = True
    ai_provider_mode: str
    telemetry: Dict[str, Any]


class AIClassifyRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=2000)
    location_hint: Optional[str] = None


class AIClassifyResponse(BaseModel):
    category: str
    sub_category: Optional[str] = None
    confidence: float
    severity: int
    evidence_signals: list[str]
    method: str
    model: str
    fallback_used: bool


@router.get("/status", response_model=AIStatusResponse)
async def get_ai_status():
    """
    Returns sanitized operational status of the primary AI provider and telemetry.
    Never exposes API keys or secrets.
    """
    telemetry_data = groq_provider.get_telemetry()
    return AIStatusResponse(
        provider="groq",
        configured=groq_provider.is_configured,
        model=groq_provider.model,
        status=groq_provider.status,
        fallback_enabled=True,
        ai_provider_mode=getattr(settings, "AI_PROVIDER", "auto"),
        telemetry=telemetry_data["telemetry"],
    )


@router.get("/telemetry")
async def get_ai_telemetry():
    """
    Returns AI inference metrics including latency, token usage, and fallback rates.
    """
    return groq_provider.get_telemetry()


@router.post("/classify", response_model=AIClassifyResponse)
async def test_ai_classification(req: AIClassifyRequest):
    """
    Test endpoint for weather classification through active AI provider (Groq or Fallback).
    """
    classifier = EventClassifier()
    meta = {"location_name": req.location_hint} if req.location_hint else None
    result: ClassificationResult = await classifier.classify(req.text, metadata=meta)

    return AIClassifyResponse(
        category=result.category,
        sub_category=result.sub_category,
        confidence=result.confidence,
        severity=result.severity,
        evidence_signals=result.evidence_signals,
        method=result.method,
        model=result.model,
        fallback_used=result.fallback_used,
    )
