"""
Integration Tests for SkyPulse AI & ML Pipeline.
Validates:
- EventClassifier integration with ML Inference Service and FallbackAIProvider
- Seamless execution when ML model is NOT_TRAINED vs when mock trained model is active
- End-to-end report processing with ML-derived embeddings and classifications
- DWEG and Verification engine compatibility with ML features
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from ai.event_classifier import EventClassifier
from ai.fallback_provider import FallbackAIProvider
from ml.inference_service import ml_inference_service
from ml.schemas import (
    ModelStatus,
    WeatherEventCategory,
    MLClassificationOutput,
)
from app.models.weather_report import WeatherReport
from app.models.source import Source
from workers.ai_pipeline import process_report_ai


@pytest.mark.asyncio
async def test_event_classifier_fallback_when_ml_untrained():
    classifier = EventClassifier()
    # When ML is untrained, classifier transparently uses FallbackAIProvider
    result = await classifier.classify("Torrential rain and heavy downpour across Mumbai suburbs")
    assert result.category == "RAINFALL"
    assert result.confidence >= 0.70
    assert result.method == "fallback_heuristic"


@pytest.mark.asyncio
async def test_event_classifier_with_active_ml_model():
    from unittest.mock import AsyncMock
    classifier = EventClassifier()
    mock_ml_res = MLClassificationOutput(
        category=WeatherEventCategory.HEATWAVE,
        confidence=0.88,
        severity=3,
        probabilities={"HEATWAVE": 0.88, "STRONG_WINDS": 0.08, "UNKNOWN": 0.04},
        model_name="weather_event_classifier",
        model_version="1.0.0",
        status="PREDICTED",
    )
    
    with patch("ai.event_classifier.ml_inference_service.classify_event", new_callable=AsyncMock) as mock_classify:
        mock_classify.return_value = mock_ml_res
        result = await classifier.classify("Extreme scorching temperatures recorded in Nagpur")
        assert result.category == "HEATWAVE"
        assert result.confidence == 0.88
        assert result.method == "ml_model"
        assert result.model == "weather_event_classifier:1.0.0"
        assert result.fallback_used is False


@pytest.mark.asyncio
async def test_ai_pipeline_with_ml_embeddings(db_session: AsyncSession):
    # 1. Create source
    src = Source(
        id=uuid.uuid4(),
        name="IMD Mumbai Station",
        source_type="GOVERNMENT_API",
        connector_class="IMDConnector",
        trust_score=0.95,
        is_active=True,
    )
    db_session.add(src)
    await db_session.flush()
    
    # 2. Create raw weather report
    rep = WeatherReport(
        id=uuid.uuid4(),
        source_id=src.id,
        raw_content="Heavy rainfall and waterlogging reported near Dadar station, Mumbai",
        normalized_text="Heavy rainfall and waterlogging reported near Dadar station, Mumbai",
        location_city="Mumbai",
        location_state="Maharashtra",
        location_lat=19.0178,
        location_lon=72.8478,
        metadata_={},
    )
    db_session.add(rep)
    await db_session.flush()
    
    # 3. Run AI processing
    processed_rep = await process_report_ai(str(rep.id), db=db_session)
    
    assert processed_rep is not None
    assert processed_rep.primary_category in ["RAINFALL", "FLOODING"]
    # Verify 384-dimensional dense semantic embedding was computed
    assert processed_rep.text_embedding is not None
    assert len(processed_rep.text_embedding) == 384
    assert processed_rep.canonical_event_id is not None
