"""
SkyPulse Regional Weather Intelligence Discovery Engine
=======================================================
Discovers, normalises, deduplicates, geolocates, classifies, and verifies
weather signals from regional Indian news, public RSS/Atom feeds,
Government/IMD/NDMA alert feeds, and Google News RSS.

Sub-modules
-----------
india_locations        – Structured India location database (states/districts/cities)
multilingual_keywords  – 11-language weather keyword dictionaries
query_engine           – LOCATION × EVENT × LANGUAGE query generator
regional_rss           – Regional news RSS + government alert feed polling
gnews_discovery        – Google News RSS discovery layer
regional_discovery_connector – Main connector wired into the orchestrator
"""


def __getattr__(name):
    """Lazy-load sub-module exports to avoid circular imports at package init time."""
    if name in ("RegionalDiscoveryConnector", "regional_discovery_connector"):
        from connectors.weather_discovery.regional_discovery_connector import (
            RegionalDiscoveryConnector as _RC,
            regional_discovery_connector as _rdc,
        )
        globals()["RegionalDiscoveryConnector"] = _RC
        globals()["regional_discovery_connector"] = _rdc
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "RegionalDiscoveryConnector",
    "regional_discovery_connector",
]

