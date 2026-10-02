import re
import math
import random
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

from connectors.schema import CanonicalRawEvent, NormalizedEvent, MediaItem
from app.models.enums import WeatherCategory
from connectors.idempotency import idempotency_service

INDIA_LAT_MIN, INDIA_LAT_MAX = 6.5, 37.6
INDIA_LON_MIN, INDIA_LON_MAX = 68.0, 97.5

# Reference geographic dataset of Indian metropolitan areas, cities, and districts
INDIAN_CITIES_REFERENCE: Dict[str, Dict[str, Any]] = {
    "mumbai": {"city": "Mumbai", "district": "Mumbai City", "state": "Maharashtra", "lat": 19.0760, "lon": 72.8777},
    "pune": {"city": "Pune", "district": "Pune", "state": "Maharashtra", "lat": 18.5204, "lon": 73.8567},
    "nagpur": {"city": "Nagpur", "district": "Nagpur", "state": "Maharashtra", "lat": 21.1458, "lon": 79.0882},
    "delhi": {"city": "Delhi", "district": "New Delhi", "state": "Delhi", "lat": 28.6139, "lon": 77.2090},
    "new delhi": {"city": "New Delhi", "district": "New Delhi", "state": "Delhi", "lat": 28.6139, "lon": 77.2090},
    "bengaluru": {"city": "Bengaluru", "district": "Bengaluru Urban", "state": "Karnataka", "lat": 12.9716, "lon": 77.5946},
    "bangalore": {"city": "Bengaluru", "district": "Bengaluru Urban", "state": "Karnataka", "lat": 12.9716, "lon": 77.5946},
    "mysuru": {"city": "Mysuru", "district": "Mysuru", "state": "Karnataka", "lat": 12.2958, "lon": 76.6394},
    "chennai": {"city": "Chennai", "district": "Chennai", "state": "Tamil Nadu", "lat": 13.0827, "lon": 80.2707},
    "coimbatore": {"city": "Coimbatore", "district": "Coimbatore", "state": "Tamil Nadu", "lat": 11.0168, "lon": 76.9558},
    "madurai": {"city": "Madurai", "district": "Madurai", "state": "Tamil Nadu", "lat": 9.9252, "lon": 78.1198},
    "kolkata": {"city": "Kolkata", "district": "Kolkata", "state": "West Bengal", "lat": 22.5726, "lon": 88.3639},
    "howrah": {"city": "Howrah", "district": "Howrah", "state": "West Bengal", "lat": 22.5958, "lon": 88.2636},
    "hyderabad": {"city": "Hyderabad", "district": "Hyderabad", "state": "Telangana", "lat": 17.3850, "lon": 78.4867},
    "ahmedabad": {"city": "Ahmedabad", "district": "Ahmedabad", "state": "Gujarat", "lat": 23.0225, "lon": 72.5714},
    "surat": {"city": "Surat", "district": "Surat", "state": "Gujarat", "lat": 21.1702, "lon": 72.8311},
    "jaipur": {"city": "Jaipur", "district": "Jaipur", "state": "Rajasthan", "lat": 26.9124, "lon": 75.7873},
    "jodhpur": {"city": "Jodhpur", "district": "Jodhpur", "state": "Rajasthan", "lat": 26.2389, "lon": 73.0243},
    "lucknow": {"city": "Lucknow", "district": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8467, "lon": 80.9462},
    "kanpur": {"city": "Kanpur", "district": "Kanpur Nagar", "state": "Uttar Pradesh", "lat": 26.4499, "lon": 80.3319},
    "varanasi": {"city": "Varanasi", "district": "Varanasi", "state": "Uttar Pradesh", "lat": 25.3176, "lon": 82.9739},
    "bhopal": {"city": "Bhopal", "district": "Bhopal", "state": "Madhya Pradesh", "lat": 23.2599, "lon": 77.4126},
    "indore": {"city": "Indore", "district": "Indore", "state": "Madhya Pradesh", "lat": 22.7196, "lon": 75.8577},
    "patna": {"city": "Patna", "district": "Patna", "state": "Bihar", "lat": 25.5941, "lon": 85.1376},
    "guwahati": {"city": "Guwahati", "district": "Kamrup Metropolitan", "state": "Assam", "lat": 26.1445, "lon": 91.7362},
    "bhubaneswar": {"city": "Bhubaneswar", "district": "Khurda", "state": "Odisha", "lat": 20.2961, "lon": 85.8245},
    "puri": {"city": "Puri", "district": "Puri", "state": "Odisha", "lat": 19.8135, "lon": 85.8312},
    "shimla": {"city": "Shimla", "district": "Shimla", "state": "Himachal Pradesh", "lat": 31.1048, "lon": 77.1734},
    "srinagar": {"city": "Srinagar", "district": "Srinagar", "state": "Jammu & Kashmir", "lat": 34.0837, "lon": 74.7973},
    "chandigarh": {"city": "Chandigarh", "district": "Chandigarh", "state": "Punjab", "lat": 30.7333, "lon": 76.7794},
    "thiruvananthapuram": {"city": "Thiruvananthapuram", "district": "Thiruvananthapuram", "state": "Kerala", "lat": 8.5241, "lon": 76.9366},
    "kochi": {"city": "Kochi", "district": "Ernakulam", "state": "Kerala", "lat": 9.9312, "lon": 76.2673},
    "visakhapatnam": {"city": "Visakhapatnam", "district": "Visakhapatnam", "state": "Andhra Pradesh", "lat": 17.6868, "lon": 83.2185},
    "dehradun": {"city": "Dehradun", "district": "Dehradun", "state": "Uttarakhand", "lat": 30.3165, "lon": 78.0322},
    "ranchi": {"city": "Ranchi", "district": "Ranchi", "state": "Jharkhand", "lat": 23.3441, "lon": 85.3096},
    "raipur": {"city": "Raipur", "district": "Raipur", "state": "Chhattisgarh", "lat": 21.2514, "lon": 81.6296},
    "panaji": {"city": "Panaji", "district": "North Goa", "state": "Goa", "lat": 15.4909, "lon": 73.8278},
}


INDIAN_STATES_REFERENCE: Dict[str, str] = {
    "maharashtra": "Maharashtra",
    "kerala": "Kerala",
    "odisha": "Odisha",
    "orissa": "Odisha",
    "karnataka": "Karnataka",
    "tamil nadu": "Tamil Nadu",
    "andhra pradesh": "Andhra Pradesh",
    "telangana": "Telangana",
    "gujarat": "Gujarat",
    "rajasthan": "Rajasthan",
    "uttar pradesh": "Uttar Pradesh",
    "madhya pradesh": "Madhya Pradesh",
    "bihar": "Bihar",
    "west bengal": "West Bengal",
    "assam": "Assam",
    "punjab": "Punjab",
    "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh",
    "himachal": "Himachal Pradesh",
    "uttarakhand": "Uttarakhand",
    "jammu": "Jammu & Kashmir",
    "kashmir": "Jammu & Kashmir",
    "jammu & kashmir": "Jammu & Kashmir",
    "jharkhand": "Jharkhand",
    "chhattisgarh": "Chhattisgarh",
    "goa": "Goa",
    "delhi": "Delhi",
    "tripura": "Tripura",
    "meghalaya": "Meghalaya",
    "manipur": "Manipur",
    "nagaland": "Nagaland",
    "mizoram": "Mizoram",
    "arunachal pradesh": "Arunachal Pradesh",
    "sikkim": "Sikkim",
    "ladakh": "Ladakh",
}


def sanitize_text(text: str, max_chars: int = 2000) -> str:
    """Strip dangerous characters, null bytes, and excess whitespace."""
    if not text:
        return ""
    # Remove null bytes and non-printable control characters (except newline, tab)
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    cleaned = " ".join(cleaned.split())
    return cleaned[:max_chars]


def normalize_category(raw_category: Optional[str], text: Optional[str] = None) -> str:
    """
    Map raw category strings to documented WeatherCategory enum.
    Ambiguous raw signals default to UNKNOWN to allow AI pipeline processing.
    """
    candidate = (raw_category or "").strip().upper()

    valid_categories = {c.value for c in WeatherCategory}
    if candidate in valid_categories:
        return candidate

    # Look for obvious unambiguous keywords in raw_category or text
    combined = f"{candidate} {text or ''}".lower()
    if any(w in combined for w in ["cyclone", "super cyclone", "typhoon"]):
        return WeatherCategory.CYCLONE.value
    if any(w in combined for w in ["hail", "hailstorm"]):
        return WeatherCategory.HAILSTORM.value
    if any(w in combined for w in ["flood", "flooding", "waterlogging", "waterlogged", "inundated", "submerged", "water level", "knee-deep"]):
        return WeatherCategory.FLOODING.value
    if any(w in combined for w in ["thunderstorm", "lightning"]):
        return WeatherCategory.THUNDERSTORM.value
    if any(w in combined for w in ["heavy rain", "downpour", "rainfall", "rain", "monsoon"]):
        return WeatherCategory.RAINFALL.value
    if any(w in combined for w in ["heatwave", "heat wave", "extreme heat", "loo"]):
        return WeatherCategory.HEATWAVE.value
    if any(w in combined for w in ["dense fog", "fog"]):
        return WeatherCategory.FOG.value
    if any(w in combined for w in ["dust storm", "andhi", "sandstorm"]):
        return WeatherCategory.DUST_STORM.value
    if any(w in combined for w in ["strong winds", "gale", "squall"]):
        return WeatherCategory.STRONG_WINDS.value
    if any(w in combined for w in ["snowfall", "snow"]):
        return WeatherCategory.SNOWFALL.value
    if any(w in combined for w in ["smog", "air pollution"]):
        return WeatherCategory.SMOG.value

    return WeatherCategory.UNKNOWN.value


def enrich_location(
    lat: Optional[float],
    lon: Optional[float],
    city: Optional[str] = None,
    district: Optional[str] = None,
    state: Optional[str] = None,
    text: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str], Optional[str], str, str, bool, bool, Optional[str]]:
    """
    Resolves and enriches location within India boundaries.
    Strictly follows provenance: never invents GPS coordinates from text-only mentions.

    Returns:
    (lat, lon, city, district, state, location_source, location_confidence, is_india_valid, is_quarantined, quarantine_reason)
    """
    # 1. Priority 1: Explicit coordinates
    if lat is not None and lon is not None:
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            if INDIA_LAT_MIN <= lat_f <= INDIA_LAT_MAX and INDIA_LON_MIN <= lon_f <= INDIA_LON_MAX:
                closest = None
                min_dist = float("inf")
                for ref_name, ref in INDIAN_CITIES_REFERENCE.items():
                    d = math.hypot(lat_f - ref["lat"], lon_f - ref["lon"])
                    if d < min_dist:
                        min_dist = d
                        closest = ref

                c_name = city or (closest["city"] if closest and min_dist < 0.25 else None)
                d_name = district or (closest["district"] if closest and min_dist < 0.25 else None)
                s_name = state or (closest["state"] if closest and min_dist < 0.25 else None)
                return lat_f, lon_f, c_name, d_name, s_name, "COORDINATES", "HIGH", True, False, None
            else:
                # Foreign coordinates
                return lat_f, lon_f, city, district, state, "COORDINATES", "LOW", False, True, "FOREIGN_COORDINATES"
        except (ValueError, TypeError):
            pass

    # 2. Priority 2 & 3: Structured Metadata & Explicit City / District / State
    if city:
        city_clean = city.strip().lower()
        if city_clean in INDIAN_CITIES_REFERENCE:
            ref = INDIAN_CITIES_REFERENCE[city_clean]
            return None, None, ref["city"], ref["district"], ref["state"], "METADATA", "MEDIUM", True, False, None

    if state:
        state_clean = state.strip().lower()
        if state_clean in INDIAN_STATES_REFERENCE:
            return None, None, city, district, INDIAN_STATES_REFERENCE[state_clean], "METADATA", "MEDIUM", True, False, None

    # 3. Priority 4: Recognized Indian Place-Name match in Text
    if text:
        text_lower = text.lower()
        # Check city matches
        for ref_key, ref in INDIAN_CITIES_REFERENCE.items():
            # word boundary match or hashtag match (e.g. #mumbairain, #mumbai, mumbai)
            pattern = r"(?:#|\b)" + re.escape(ref_key) + r"(?:rain|weather|alert|\b)"
            if re.search(pattern, text_lower):
                return None, None, ref["city"], ref["district"], ref["state"], "TEXT", "MEDIUM", True, False, None

        # Check state matches
        for st_key, st_name in INDIAN_STATES_REFERENCE.items():
            pattern = r"(?:#|\b)" + re.escape(st_key) + r"(?:rain|weather|alert|\b)"
            if re.search(pattern, text_lower):
                return None, None, None, None, st_name, "TEXT", "MEDIUM", True, False, None

    # 4. Priority 5: Otherwise UNKNOWN
    return None, None, None, None, None, "UNKNOWN", "LOW", False, True, "UNKNOWN_LOCATION"


async def normalize_raw_event(event: CanonicalRawEvent) -> NormalizedEvent:
    """
    Normalizes a canonical raw event into a validated and geocoded NormalizedEvent.
    Calculates idempotency key and generates tracking ID.
    """
    # 1. Sanitize text
    clean_text = sanitize_text(event.text)

    # 2. Category normalization
    category = normalize_category(event.suggested_category, clean_text)

    # 3. Severity
    severity = event.severity if event.severity in (1, 2, 3, 4) else 2

    # 4. Location enrichment
    lat, lon, city, district, state, loc_source, loc_conf, is_india, is_quar, quar_reason = enrich_location(
        lat=event.latitude,
        lon=event.longitude,
        city=event.city,
        district=event.district,
        state=event.state,
        text=clean_text,
    )

    # 5. Idempotency key
    key = event.idempotency_key or idempotency_service.compute_key(
        source_id=event.source_id,
        external_id=event.external_id,
        text=clean_text,
        observed_at=event.observed_at,
        latitude=lat,
        longitude=lon,
    )
    is_duplicate = await idempotency_service.is_duplicate(key)

    # 6. Issue SP- tracking ID
    year = event.observed_at.year if event.observed_at else datetime.now(timezone.utc).year
    rand_seq = random.randint(100000, 999999)
    tracking_id = f"SP-{year}-{rand_seq}"

    return NormalizedEvent(
        ingestion_id=event.ingestion_id,
        source_id=event.source_id,
        source_type=event.source_type,
        external_id=event.external_id,
        tracking_id=tracking_id,
        text=clean_text,
        primary_category=category,
        severity=severity,
        latitude=lat,
        longitude=lon,
        city=city,
        district=district,
        state=state,
        location_source=loc_source,
        location_confidence=loc_conf,
        is_india_valid=is_india,
        is_quarantined=is_quar,
        quarantine_reason=quar_reason,
        observed_at=event.observed_at,
        ingested_at=event.ingested_at,
        media=event.media,
        metadata={"raw_payload": event.raw_payload},
        is_demo=event.is_demo,
        is_duplicate=is_duplicate,
        idempotency_key=key,
    )
