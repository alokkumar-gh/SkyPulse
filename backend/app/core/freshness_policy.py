"""
SkyPulse Weather Intelligence Freshness & Event Lifecycle Policies
==================================================================
Defines authoritative, category-aware Time-To-Live (TTL) durations,
staleness thresholds, and lifecycle state transition rules.

Guarantees:
- Event markers expire based on meteorological phenomenon characteristics.
- Weather observations have clear freshness tiers (LIVE, RECENT, STALE, NO_DATA).
- Lifecycle status (DETECTED, ACTIVE, STALE, EXPIRED) is strictly decoupled from
  verification status (UNVERIFIED, CORROBORATED, VERIFIED, CONTRADICTED).
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Configurable Category TTL Policies (in hours) — 48h Live Intelligence Window
# ---------------------------------------------------------------------------
EVENT_FRESHNESS_POLICY: Dict[str, Dict[str, float]] = {
    # High-transience convective events
    "THUNDERSTORM": {
        "base_ttl_hours": 2.0,
        "stale_threshold_hours": 1.0,
        "severity_multiplier": 0.5,
    },
    "HAILSTORM": {
        "base_ttl_hours": 2.5,
        "stale_threshold_hours": 1.25,
        "severity_multiplier": 0.5,
    },
    "STRONG_WINDS": {
        "base_ttl_hours": 3.0,
        "stale_threshold_hours": 1.5,
        "severity_multiplier": 0.5,
    },
    "RAINFALL": {
        "base_ttl_hours": 3.5,
        "stale_threshold_hours": 1.75,
        "severity_multiplier": 0.75,
    },
    "FOG": {
        "base_ttl_hours": 4.0,
        "stale_threshold_hours": 2.0,
        "severity_multiplier": 0.5,
    },
    "DUST_STORM": {
        "base_ttl_hours": 4.5,
        "stale_threshold_hours": 2.0,
        "severity_multiplier": 1.0,
    },
    "SMOG": {
        "base_ttl_hours": 8.0,
        "stale_threshold_hours": 4.0,
        "severity_multiplier": 1.0,
    },
    "SNOWFALL": {
        "base_ttl_hours": 12.0,
        "stale_threshold_hours": 6.0,
        "severity_multiplier": 2.0,
    },
    # Sustained hazards
    "HEATWAVE": {
        "base_ttl_hours": 24.0,
        "stale_threshold_hours": 12.0,
        "severity_multiplier": 4.0,
    },
    "LANDSLIDE": {
        "base_ttl_hours": 36.0,
        "stale_threshold_hours": 18.0,
        "severity_multiplier": 6.0,
    },
    "FLOODING": {
        "base_ttl_hours": 36.0,
        "stale_threshold_hours": 18.0,
        "severity_multiplier": 6.0,
    },
    "FLOOD": {
        "base_ttl_hours": 36.0,
        "stale_threshold_hours": 18.0,
        "severity_multiplier": 6.0,
    },
    "CYCLONE": {
        "base_ttl_hours": 48.0,
        "stale_threshold_hours": 24.0,
        "severity_multiplier": 12.0,
    },
    "WEATHER_OBSERVATION": {
        "base_ttl_hours": 3.0,
        "stale_threshold_hours": 0.75,
        "severity_multiplier": 0.0,
    },
    "UNKNOWN": {
        "base_ttl_hours": 6.0,
        "stale_threshold_hours": 3.0,
        "severity_multiplier": 1.0,
    },
}

# ---------------------------------------------------------------------------
# Section 4: Live Weather Intelligence Freshness Tiers (Hours)
# ---------------------------------------------------------------------------
NEWS_FRESHNESS_TIERS = {
    "LIVE": 6.0,       # 0 - 6 hours: Breaking / Real-time live intelligence
    "RECENT": 24.0,    # 6 - 24 hours: Recent reporting from today
    "STALE": 48.0,     # 24 - 48 hours: Older than 1 day, transitioning out of live
    # > 48 hours: ARCHIVED (Leaves LIVE weather news, retained in historical archive)
}


def compute_news_freshness_status(
    published_at: Optional[datetime],
    updated_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> str:
    """
    Computes authoritative news freshness tier using source publication / update time:
    - LIVE: 0 to 6 hours
    - RECENT: 6 to 24 hours
    - STALE: 24 to 48 hours
    - ARCHIVED: > 48 hours
    """
    ref = updated_at or published_at
    if ref is None:
        return "RECENT"

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)

    diff_hours = (now - ref).total_seconds() / 3600.0
    if diff_hours < 0:
        return "LIVE"
    elif diff_hours <= NEWS_FRESHNESS_TIERS["LIVE"]:
        return "LIVE"
    elif diff_hours <= NEWS_FRESHNESS_TIERS["RECENT"]:
        return "RECENT"
    elif diff_hours <= NEWS_FRESHNESS_TIERS["STALE"]:
        return "STALE"
    else:
        return "ARCHIVED"

# ---------------------------------------------------------------------------
# Baseline Weather Observation Freshness Tiers (Minutes)
# ---------------------------------------------------------------------------
OBSERVATION_FRESHNESS_TIERS = {
    "LIVE": 15.0,     # <= 15 minutes: Real-time telemetry
    "RECENT": 45.0,   # 15 - 45 minutes: Recent observation
    "STALE": 180.0,   # 45 - 180 minutes: Stale telemetry (marked with badge)
    # > 180 minutes: NO_DATA / EXPIRED
}


def get_category_policy(category: Optional[str]) -> Dict[str, float]:
    """Retrieves the freshness policy dictionary for a given category."""
    cat = (category or "UNKNOWN").upper().strip()
    return EVENT_FRESHNESS_POLICY.get(cat, EVENT_FRESHNESS_POLICY["UNKNOWN"])


def calculate_event_expiry(
    category: Optional[str],
    reference_time: Optional[datetime],
    severity: int = 1,
) -> datetime:
    """
    Computes server-authoritative event expiration datetime based on category policy
    and severity scaling.
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    elif reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)

    policy = get_category_policy(category)
    base_ttl = policy["base_ttl_hours"]
    multiplier = policy.get("severity_multiplier", 0.0)
    extra_hours = max(0, severity - 1) * multiplier
    total_hours = base_ttl + extra_hours

    return reference_time + timedelta(hours=total_hours)


def calculate_event_staleness_threshold(
    category: Optional[str],
    reference_time: Optional[datetime],
    severity: int = 1,
) -> datetime:
    """Computes the timestamp after which an active event is flagged as STALE."""
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    elif reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)

    policy = get_category_policy(category)
    stale_hours = policy["stale_threshold_hours"]
    multiplier = policy.get("severity_multiplier", 0.0) * 0.5
    extra_hours = max(0, severity - 1) * multiplier

    return reference_time + timedelta(hours=stale_hours + extra_hours)


def determine_event_lifecycle_status(
    *,
    category: Optional[str] = None,
    is_active: bool = True,
    is_deleted: bool = False,
    resolved_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    last_seen_at: Optional[datetime] = None,
    severity: int = 1,
    evidence_count: int = 1,
    now: Optional[datetime] = None,
) -> str:
    """
    Evaluates current server-side lifecycle state:
    DETECTED -> ACTIVE -> STALE -> EXPIRED
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if is_deleted or not is_active:
        return "EXPIRED"

    if resolved_at is not None:
        if resolved_at.tzinfo is None:
            resolved_at = resolved_at.replace(tzinfo=timezone.utc)
        if now >= resolved_at:
            return "EXPIRED"

    # Compute effective expiry
    eff_expires_at = expires_at
    if eff_expires_at is None:
        ref = last_seen_at or now
        eff_expires_at = calculate_event_expiry(category, ref, severity)
    elif eff_expires_at.tzinfo is None:
        eff_expires_at = eff_expires_at.replace(tzinfo=timezone.utc)

    if now >= eff_expires_at:
        return "EXPIRED"

    # Compute stale threshold
    ref_time = last_seen_at or now
    stale_thresh = calculate_event_staleness_threshold(category, ref_time, severity)
    if now >= stale_thresh:
        return "STALE"

    if evidence_count <= 1:
        return "DETECTED"

    return "ACTIVE"


def get_observation_freshness_category(
    observed_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> Tuple[str, float]:
    """
    Calculates observation freshness tier and elapsed age in minutes:
    Returns (tier, age_minutes) where tier in ('LIVE', 'RECENT', 'STALE', 'NO_DATA').
    """
    if observed_at is None:
        return ("NO_DATA", 999999.0)

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)

    delta = now - observed_at
    age_minutes = max(0.0, delta.total_seconds() / 60.0)

    if age_minutes <= OBSERVATION_FRESHNESS_TIERS["LIVE"]:
        return ("LIVE", age_minutes)
    elif age_minutes <= OBSERVATION_FRESHNESS_TIERS["RECENT"]:
        return ("RECENT", age_minutes)
    elif age_minutes <= OBSERVATION_FRESHNESS_TIERS["STALE"]:
        return ("STALE", age_minutes)
    else:
        return ("NO_DATA", age_minutes)


def format_freshness_label(observed_at: Optional[datetime], now: Optional[datetime] = None) -> str:
    """Returns human-readable, honest freshness label like 'LIVE · 2 min ago'."""
    tier, age_mins = get_observation_freshness_category(observed_at, now)
    if tier == "NO_DATA":
        return "NO CURRENT TELEMETRY"

    if age_mins < 1.0:
        return f"{tier} · Just now"
    elif age_mins < 60.0:
        return f"{tier} · {int(age_mins)} min ago"
    else:
        hrs = int(age_mins // 60)
        return f"{tier} · {hrs}h ago"
