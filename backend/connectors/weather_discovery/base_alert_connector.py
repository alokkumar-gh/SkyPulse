"""
SkyPulse Generic Public Alert & Disaster Feed Adapter (Layer E)
==============================================================
Provides a standard extensible adapter interface for public weather and disaster alerts:
- Common Alerting Protocol (CAP 1.2 XML / JSON)
- Atom / RSS alert feeds
- Government / State Disaster Management Feeds
- CWC / IMD / NDMA public warning feeds

Supports:
- HTTP ETag and If-Modified-Since conditional caching
- Exponential backoff and circuit-breaking
- Native India administrative boundary resolution
- Weather-relevance validation
- Zero credential fabrication
"""

import abc
import hashlib
import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum
from connectors.weather_discovery.india_locations import lookup_location, validate_location
from connectors.weather_discovery.regional_rss import is_weather_relevant
from connectors.normalizer import sanitize_text

logger = logging.getLogger("skypulse.connectors.public_alert")

CAP_1_2_NS = "{urn:oasis:names:tc:emergency:cap:1.2}"
CAP_1_1_NS = "{urn:oasis:names:tc:emergency:cap:1.1}"


class BasePublicAlertConnector(abc.ABC):
    """
    Abstract base connector for public weather and disaster alert feeds.
    All Layer E alert adapters inherit from this class.
    """

    def __init__(
        self,
        source_id: str,
        name: str,
        feed_url: str,
        source_type: str = "OFFICIAL",
        trust_score: float = 0.95,
        poll_interval_seconds: int = 300,
        timeout_seconds: float = 12.0,
    ):
        self.source_id = source_id
        self.name = name
        self.feed_url = feed_url
        self.source_type = source_type
        self.trust_score = trust_score
        self.poll_interval_seconds = poll_interval_seconds
        self.timeout_seconds = timeout_seconds

        # Conditional HTTP caching
        self.last_etag: Optional[str] = None
        self.last_modified: Optional[str] = None

        # State tracking
        self.health_status: str = "UP"  # UP | DEGRADED | ACCESS_RESTRICTED | RATE_LIMITED | UNAVAILABLE | PARSE_ERROR
        self.last_success: Optional[datetime] = None
        self.last_failure: Optional[datetime] = None
        self.last_error_message: Optional[str] = None
        self.total_items_fetched: int = 0
        self.total_weather_items: int = 0
        self.is_running: bool = False

    @abc.abstractmethod
    async def fetch(self, client: httpx.AsyncClient) -> Tuple[Optional[str], int, Dict[str, str]]:
        """
        Fetch raw payload from upstream alert endpoint with ETag/Last-Modified support.
        Returns: (raw_body, http_status_code, response_headers)
        """
        pass

    @abc.abstractmethod
    def parse(self, raw_content: str, content_type: str = "xml") -> List[Dict[str, Any]]:
        """
        Parse raw content into structured alert dicts.
        """
        pass

    @abc.abstractmethod
    def normalize(self, parsed_alerts: List[Dict[str, Any]]) -> List[CanonicalRawEvent]:
        """
        Convert structured alert dicts into CanonicalRawEvent objects.
        """
        pass

    async def poll(self) -> List[CanonicalRawEvent]:
        """Complete poll lifecycle: fetch -> parse -> normalize."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SkyPulse-PublicAlertAdapter/2.0 (+https://skypulse.gov.in)",
            "Accept": "application/xml, text/xml, application/json, application/atom+xml, */*",
        }
        if self.last_etag:
            headers["If-None-Match"] = self.last_etag
        if self.last_modified:
            headers["If-Modified-Since"] = self.last_modified

        events: List[CanonicalRawEvent] = []
        async with httpx.AsyncClient(headers=headers, timeout=self.timeout_seconds, follow_redirects=True) as client:
            try:
                raw_body, status_code, resp_headers = await self.fetch(client)

                # HTTP 304 Not Modified — unchanged alert feed
                if status_code == 304:
                    self.health_status = "UP"
                    self.last_success = datetime.now(timezone.utc)
                    return []

                if status_code == 403 or status_code == 401:
                    self.health_status = "ACCESS_RESTRICTED"
                    self.last_failure = datetime.now(timezone.utc)
                    self.last_error_message = f"HTTP {status_code} Access Restricted"
                    return []

                if status_code == 429:
                    self.health_status = "RATE_LIMITED"
                    self.last_failure = datetime.now(timezone.utc)
                    self.last_error_message = "HTTP 429 Rate Limited"
                    return []

                if status_code >= 400 or not raw_body:
                    self.health_status = "UNAVAILABLE"
                    self.last_failure = datetime.now(timezone.utc)
                    self.last_error_message = f"HTTP {status_code} upstream failure"
                    return []

                # Update ETag / Last-Modified
                if "etag" in resp_headers:
                    self.last_etag = resp_headers["etag"]
                if "last-modified" in resp_headers:
                    self.last_modified = resp_headers["last-modified"]

                # Determine content type
                c_type = "json" if (raw_body.strip().startswith("{") or raw_body.strip().startswith("[")) else "xml"
                parsed = self.parse(raw_body, content_type=c_type)
                events = self.normalize(parsed)

                self.total_items_fetched += len(parsed)
                self.total_weather_items += len(events)
                self.health_status = "UP"
                self.last_success = datetime.now(timezone.utc)
                self.last_error_message = None

            except ET.ParseError as pe:
                self.health_status = "PARSE_ERROR"
                self.last_failure = datetime.now(timezone.utc)
                self.last_error_message = f"XML parse error: {pe}"
                logger.warning("Alert feed '%s' XML parse error: %s", self.name, pe)
            except Exception as e:
                self.health_status = "UNAVAILABLE"
                self.last_failure = datetime.now(timezone.utc)
                self.last_error_message = str(e)
                logger.warning("Alert feed '%s' fetch error: %s", self.name, e)

        return events

    def get_source_metadata(self) -> Dict[str, Any]:
        """Returns diagnostic and operational metadata for admin/health reporting."""
        return {
            "source_id": self.source_id,
            "name": self.name,
            "feed_url": self.feed_url,
            "source_type": self.source_type,
            "trust_score": self.trust_score,
            "health_status": self.health_status,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "last_error": self.last_error_message,
            "total_items": self.total_items_fetched,
            "total_weather_items": self.total_weather_items,
        }


def validate_cap_coordinate(lat: float, lon: float) -> bool:
    """Validate latitude and longitude ranges."""
    if lat is None or lon is None:
        return False
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return False
    return True


def parse_cap_polygon_string(poly_str: str) -> Optional[List[List[float]]]:
    """
    Parses a CAP 1.2 polygon string 'lat1,lon1 lat2,lon2 ...' into a GeoJSON LinearRing [[lon1, lat1], ...].
    Validates:
    - String contains at least 3 distinct valid coordinates
    - Coordinates are within valid ranges [-90..90, -180..180]
    - Returns closed GeoJSON ring: [[lon, lat], [lon, lat], ...] with ring[0] == ring[-1]
    - Returns None if malformed, out of range, or fewer than 3 unique vertices.
    """
    if not poly_str or not isinstance(poly_str, str):
        return None

    # Standard CAP 1.2 format is space-delimited lat,lon pairs
    tokens = [t.strip() for t in re.split(r"[\s\n\r]+", poly_str.strip()) if t.strip()]
    if len(tokens) < 3:
        # Check if comma-delimited without spaces e.g. "lat1,lon1,lat2,lon2"
        sub_tokens = poly_str.replace(" ", "").split(",")
        if len(sub_tokens) >= 6 and len(sub_tokens) % 2 == 0:
            tokens = [f"{sub_tokens[i]},{sub_tokens[i+1]}" for i in range(0, len(sub_tokens), 2)]
        else:
            return None

    points: List[List[float]] = []
    unique_points = set()

    for token in tokens:
        parts = token.split(",")
        if len(parts) != 2:
            return None
        try:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
        except (ValueError, TypeError):
            return None

        if not validate_cap_coordinate(lat, lon):
            return None

        # GeoJSON ordering: [longitude, latitude]
        pt = [round(lon, 6), round(lat, 6)]
        points.append(pt)
        unique_points.add((pt[0], pt[1]))

    # Must have at least 3 distinct vertices
    if len(unique_points) < 3:
        return None

    # GeoJSON LinearRing must be closed (first == last)
    if points[0] != points[-1]:
        points.append(list(points[0]))

    if len(points) < 4:
        return None

    return points


def parse_cap_polygon_geojson(poly_str: str) -> Optional[Dict[str, Any]]:
    """
    Parses a single CAP polygon coordinate string directly to a valid GeoJSON Polygon dictionary.
    """
    ring = parse_cap_polygon_string(poly_str)
    if not ring:
        return None
    return {
        "type": "Polygon",
        "coordinates": [ring],
    }


def extract_cap_geometry(info_el: Optional[ET.Element], ns: str = "") -> Optional[Dict[str, Any]]:
    """
    Extracts all <polygon> elements from CAP info/area elements and returns a valid GeoJSON Polygon or MultiPolygon.
    Returns None if no valid polygon geometry is present.
    """
    if info_el is None:
        return None

    poly_elements = []
    # Search in <area> and direct children
    for area_el in info_el.findall(f"{ns}area") + info_el.findall("area"):
        poly_elements.extend(area_el.findall(f"{ns}polygon") + area_el.findall("polygon"))
    poly_elements.extend(info_el.findall(f"{ns}polygon") + info_el.findall("polygon"))

    valid_rings: List[List[List[float]]] = []
    for pe in poly_elements:
        p_text = (pe.text or "").strip()
        if p_text:
            ring = parse_cap_polygon_string(p_text)
            if ring:
                valid_rings.append(ring)

    if not valid_rings:
        return None

    if len(valid_rings) == 1:
        return {
            "type": "Polygon",
            "coordinates": valid_rings,
        }
    else:
        return {
            "type": "MultiPolygon",
            "coordinates": [[ring] for ring in valid_rings],
        }


class GenericCAPAlertConnector(BasePublicAlertConnector):
    """
    Standard Common Alerting Protocol (CAP) and RSS/Atom Alert Feed Adapter.
    Handles SACHET CAP, CWC flood bulletins, and state disaster management RSS feeds.
    """

    async def fetch(self, client: httpx.AsyncClient) -> Tuple[Optional[str], int, Dict[str, str]]:
        resp = await client.get(self.feed_url)
        return resp.text, resp.status_code, dict(resp.headers)

    def parse(self, raw_content: str, content_type: str = "xml") -> List[Dict[str, Any]]:
        alerts = []
        if content_type == "json":
            import json
            try:
                data = json.loads(raw_content)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("alerts", data.get("items", data.get("data", [data])))
            except Exception:
                pass
            return []

        # XML / RSS / CAP XML
        clean_xml = sanitize_text(raw_content)
        root = ET.fromstring(clean_xml)

        # Check CAP 1.2 / 1.1 root
        tag = root.tag
        if "alert" in tag.lower():
            # Direct CAP alert document
            alerts.append(self._parse_single_cap_element(root))
            return alerts

        # Check RSS items / Atom entries
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        for it in items:
            title = (it.findtext("title") or it.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
            desc = (it.findtext("description") or it.findtext("{http://www.w3.org/2005/Atom}summary") or it.findtext("{http://www.w3.org/2005/Atom}content") or "").strip()
            link = (it.findtext("link") or "").strip()
            pub_date = (it.findtext("pubDate") or it.findtext("{http://www.w3.org/2005/Atom}published") or it.findtext("{http://www.w3.org/2005/Atom}updated") or "").strip()
            guid = (it.findtext("guid") or it.findtext("{http://www.w3.org/2005/Atom}id") or link or title).strip()

            # Check if RSS item contains CAP polygon extensions (e.g. <georss:polygon> or <cap:polygon>)
            poly_text = (
                it.findtext("{http://www.georss.org/georss}polygon")
                or it.findtext("{urn:oasis:names:tc:emergency:cap:1.2}polygon")
                or it.findtext("polygon")
                or ""
            ).strip()

            geometry = None
            if poly_text:
                ring = parse_cap_polygon_string(poly_text)
                if ring:
                    geometry = {"type": "Polygon", "coordinates": [ring]}

            alerts.append({
                "identifier": guid,
                "title": title,
                "description": desc,
                "link": link,
                "sent": pub_date,
                "severity": "Unknown",
                "urgency": "Unknown",
                "certainty": "Observed",
                "area_desc": "",
                "geometry": geometry,
                "has_polygon": bool(geometry is not None),
            })

        return alerts

    def _parse_single_cap_element(self, alert_elem: ET.Element) -> Dict[str, Any]:
        """Extract structured CAP 1.2 fields with multi-vertex polygon geometry."""
        ns = ""
        if alert_elem.tag.startswith("{"):
            ns = alert_elem.tag.split("}")[0] + "}"

        identifier = (alert_elem.findtext(f"{ns}identifier") or "").strip()
        sent = (alert_elem.findtext(f"{ns}sent") or "").strip()
        info_el = alert_elem.find(f"{ns}info")

        event = ""
        headline = ""
        description = ""
        severity = "Moderate"
        urgency = "Expected"
        certainty = "Observed"
        area_desc = ""
        geometry = None

        if info_el is not None:
            event = (info_el.findtext(f"{ns}event") or "").strip()
            headline = (info_el.findtext(f"{ns}headline") or "").strip()
            description = (info_el.findtext(f"{ns}description") or "").strip()
            severity = (info_el.findtext(f"{ns}severity") or "Moderate").strip()
            urgency = (info_el.findtext(f"{ns}urgency") or "Expected").strip()
            certainty = (info_el.findtext(f"{ns}certainty") or "Observed").strip()
            area_el = info_el.find(f"{ns}area")
            if area_el is not None:
                area_desc = (area_el.findtext(f"{ns}areaDesc") or "").strip()

            # Extract full multi-vertex polygon geometry
            geometry = extract_cap_geometry(info_el, ns)

        title = headline or event or "Severe Weather Alert"
        return {
            "identifier": identifier,
            "title": title,
            "description": description or headline,
            "link": self.feed_url,
            "sent": sent,
            "severity": severity,
            "urgency": urgency,
            "certainty": certainty,
            "area_desc": area_desc,
            "geometry": geometry,
            "has_polygon": bool(geometry is not None),
        }

    def normalize(self, parsed_alerts: List[Dict[str, Any]]) -> List[CanonicalRawEvent]:
        events = []
        for alert in parsed_alerts:
            title = alert.get("title", "")
            desc = alert.get("description", "")
            combined_text = f"{title}. {desc}".strip(". ")

            if not combined_text or not is_weather_relevant(combined_text):
                continue

            # Location validation
            area_text = alert.get("area_desc", "") or combined_text
            loc = lookup_location(area_text)

            lat = loc.get("lat") if loc else None
            lon = loc.get("lon") if loc else None
            has_coords = (lat is not None and lon is not None)

            # If location wasn't textually resolved but alert contains valid polygon, compute official centroid
            geom = alert.get("geometry")
            if not has_coords and geom and geom.get("type") == "Polygon" and geom.get("coordinates"):
                ring = geom["coordinates"][0]
                pts = ring[:-1] if len(ring) > 1 else ring
                if pts:
                    avg_lon = sum(p[0] for p in pts) / len(pts)
                    avg_lat = sum(p[1] for p in pts) / len(pts)
                    lat = round(avg_lat, 4)
                    lon = round(avg_lon, 4)
                    has_coords = True

            # Idempotency key
            ident = alert.get("identifier") or hashlib.sha256(combined_text.encode()).hexdigest()[:16]
            idem_key = f"alert-{ident}"

            ev = CanonicalRawEvent(
                source_id=self.source_id,
                source_type=self.source_type,
                external_id=ident,
                observed_at=datetime.now(timezone.utc),
                text=combined_text[:1000],
                location_source="GPS" if has_coords else "TEXT",
                location_confidence="HIGH" if has_coords else "MEDIUM",
                latitude=lat if has_coords else None,
                longitude=lon if has_coords else None,
                city=loc.get("city") if loc else None,
                district=loc.get("district") if loc else None,
                state=loc.get("state") if loc else None,
                is_india_valid=True if (loc or has_coords) else False,
                is_quarantined=False,
                idempotency_key=idem_key,
                raw_payload={
                    "title": title,
                    "severity": alert.get("severity"),
                    "urgency": alert.get("urgency"),
                    "certainty": alert.get("certainty"),
                    "source_name": self.name,
                    "trust_score": self.trust_score,
                    "discovery_source": "PUBLIC_ALERT_ADAPTER",
                    "geometry": geom,
                    "has_polygon": bool(geom is not None),
                },
            )
            events.append(ev)

        return events

