"""
Unit Tests for SkyPulse ML Feature Extraction & Preprocessing.
Validates:
- Text normalization, multilingual detection (Devanagari, Hindi transliteration)
- Feature vector extraction (16-dim representation)
- Text token statistics & linguistic indicator triggers
- Extensibility and error handling
"""

import pytest
from datetime import datetime, timezone
from ml.preprocessing import TextPreprocessor, text_preprocessor
from ml.feature_extraction import FeatureExtractor, feature_extractor
from ml.schemas import MultiModalFeatures, TrainingRecord, WeatherEventCategory


def test_text_preprocessing_english():
    text = "  Heavy   monsoon rainfall across Mumbai district!  "
    cleaned = text_preprocessor.clean_text(text)
    assert cleaned == "Heavy monsoon rainfall across Mumbai district!"
    
    tokens = text_preprocessor.tokenize(cleaned)
    assert "heavy" in tokens
    assert "rainfall" in tokens
    assert "mumbai" in tokens


def test_text_preprocessing_multilingual_hindi():
    # Test Devanagari Hindi text
    hindi_text = "मुंबई में भारी बारिश और जलभराव"
    lang = text_preprocessor.detect_language(hindi_text)
    assert lang == "hi"
    
    # Test Hinglish transliteration detection
    hinglish_text = "Delhi me bahut tez baarish khatra aur bijli girne ki khabar hai"
    signals = text_preprocessor.extract_linguistic_signals(hinglish_text)
    assert signals["hinglish_detected"] is True
    assert signals["urgency_detected"] is True


def test_feature_extractor_16_dim_vector():
    extractor = FeatureExtractor()
    
    vector = extractor.extract_dense_vector(
        text="Torrential rain and flash flood in Chennai",
        source_trust=0.85,
        source_type="IMD_BULLETIN",
        latitude=13.0827,
        longitude=80.2707,
        event_time=datetime.now(timezone.utc),
        corroboration_count=4,
        has_media=True,
        has_imd_corroboration=True,
        has_data_gov_corroboration=False,
        has_contradictions=False,
        dweg_support_edges=3,
        dweg_contradict_edges=0,
        temp_c=28.5,
        rain_mm=65.0,
        wind_kmh=45.0,
    )
    
    assert isinstance(vector, list)
    assert len(vector) == 16
    assert all(isinstance(v, (int, float)) for v in vector)
    # Check source trust mapping
    assert vector[1] == 0.85
    # Check IMD verification indicator
    assert vector[5] == 1.0
    # Check DWEG support edge count
    assert vector[8] == 3.0


def test_feature_extractor_pydantic_schema():
    extractor = FeatureExtractor()
    features = extractor.extract_features(
        report_data={"text": "Heatwave warning in Nagpur", "source_trust": 0.90, "source_type": "IMD"},
        official_data={"agency": "IMD"},
    )
    assert isinstance(features, MultiModalFeatures)
    assert features.source_trust == 0.90
    assert features.has_imd_corroboration is True
    assert features.text_length > 0
    assert len(features.dense_feature_vector) == 16


def test_training_record_schema():
    rec = TrainingRecord(
        text="Heavy thunderstorm in Kolkata with strong gusty winds",
        category=WeatherEventCategory.THUNDERSTORM,
        severity=3,
        verified=True,
        source_type="CITIZEN",
        latitude=22.5726,
        longitude=88.3639,
    )
    assert rec.category == WeatherEventCategory.THUNDERSTORM
    assert rec.severity == 3
    assert rec.verified is True
    assert rec.language == "en"
