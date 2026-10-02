import re
import unicodedata
from typing import Dict, Any, List, Optional


# Multilingual Weather Lexicon Triggers
WEATHER_TRIGGERS = {
    "RAINFALL": ["rain", "barish", "baarish", "downpour", "rainfall", "monsoon", "drizzle", "shower", "barsat"],
    "THUNDERSTORM": ["thunder", "lightning", "toofan", "bijli", "thunderstorm", "storm", "aandhi"],
    "FLOODING": ["flood", "waterlogging", "inundated", "submerged", "pani", "jala-plavan", "waterlogged", "drainage"],
    "HEATWAVE": ["heat", "garmi", "loo", "hot", "sunstroke", "heatwave", "scorching", "tapan"],
    "FOG": ["fog", "kuhasa", "dhund", "mist", "smog", "visibility", "kohra"],
    "DUST_STORM": ["dust", "andhi", "sandstorm", "duststorm", "reyt", "haze"],
    "STRONG_WINDS": ["wind", "hawa", "gale", "gust", "cyclone", "bhavandar", "cyclonic"],
}

URGENCY_WORDS = [
    "urgent", "alert", "emergency", "danger", "hazard", "evacuate", "rescue", "trapped",
    "khatra", "bachao", "warning", "critical", "severe", "destructive", "damage"
]

HINGLISH_INDICATORS = ["bahut", "tez", "baarish", "pani", "garmi", "bijli", "aandhi", "toofan", "khabar", "hai", "me", "aur"]


def clean_weather_text(text: str, preserve_original: bool = True) -> str:
    """
    Cleans raw user/sensor text while preserving critical meteorological measurements
    (e.g., '120 mm', '45 °C', '80 km/h') and Devanagari / Latin characters.
    """
    if not text:
        return ""

    # Normalize unicode (NFKC)
    normalized = unicodedata.normalize("NFKC", text)

    # Remove URLs
    cleaned = re.sub(r"https?://\S+|www\.\S+", "", normalized)

    # Remove email addresses
    cleaned = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "", cleaned)

    # Standardize meteorological units (keep numbers and unit letters clean)
    cleaned = re.sub(r"(?<=\d)\s*(mm|cm|km/?h|kmph|°\s*c|celsius|hpa|mb)", r" \1", cleaned, flags=re.IGNORECASE)

    # Collapse excessive whitespaces and newlines
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


def extract_token_statistics(text: str) -> Dict[str, Any]:
    """
    Computes lexical features, character counts, and urgency indicators.
    """
    if not text:
        return {
            "char_length": 0,
            "word_count": 0,
            "urgency_count": 0,
            "has_devanagari": False,
            "lexical_diversity": 0.0,
        }

    words = re.findall(r"\w+", text.lower())
    word_count = len(words)
    char_length = len(text)

    # Devanagari detection (\u0900-\u097F)
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", text))

    # Urgency keyword match
    urgency_count = sum(1 for w in words if w in URGENCY_WORDS)

    # Lexical diversity (unique words / total words)
    lexical_diversity = len(set(words)) / word_count if word_count > 0 else 0.0

    return {
        "char_length": char_length,
        "word_count": word_count,
        "urgency_count": urgency_count,
        "has_devanagari": has_devanagari,
        "lexical_diversity": round(lexical_diversity, 2),
    }


def simple_tokenize(text: str, max_tokens: int = 128) -> List[int]:
    """
    Deterministic fallback byte-pair hash tokenizer for test/lightweight environments
    when full HuggingFace tokenizer library is not loaded.
    """
    cleaned = clean_weather_text(text).lower()
    words = re.findall(r"\w+", cleaned)
    tokens = []
    for w in words[:max_tokens]:
        # Hash token into vocab space of 30,000
        h = abs(hash(w)) % 30000 + 100
        tokens.append(h)

    # Pad or truncate to max_tokens
    if len(tokens) < max_tokens:
        tokens.extend([0] * (max_tokens - len(tokens)))
    return tokens[:max_tokens]


class TextPreprocessor:
    """Unified text preprocessing interface for ML tokenization and multilingual detection."""

    def clean_text(self, text: str) -> str:
        return clean_weather_text(text)

    def tokenize(self, text: str) -> List[str]:
        cleaned = clean_weather_text(text).lower()
        return re.findall(r"\w+", cleaned)

    def detect_language(self, text: str) -> str:
        if bool(re.search(r"[\u0900-\u097F]", text)):
            return "hi"
        return "en"

    def extract_linguistic_signals(self, text: str) -> Dict[str, Any]:
        cleaned = clean_weather_text(text).lower()
        words = set(re.findall(r"\w+", cleaned))
        hinglish = any(h in words for h in HINGLISH_INDICATORS)
        urgency = any(u in words for u in URGENCY_WORDS)
        return {
            "hinglish_detected": hinglish,
            "urgency_detected": urgency,
            "has_devanagari": bool(re.search(r"[\u0900-\u097F]", text)),
        }


text_preprocessor = TextPreprocessor()
