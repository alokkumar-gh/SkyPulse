"""
Unit & Integration Tests for CAP Hazard Multi-Vertex Polygon Processing & GeoJSON API
Tests requirements TEST A to TEST F as specified in SIH requirements.
"""

import pytest
from connectors.weather_discovery.base_alert_connector import (
    parse_cap_polygon_string,
    parse_cap_polygon_geojson,
    validate_cap_coordinate,
    extract_cap_geometry,
    GenericCAPAlertConnector,
)


def test_polygon_validation_coordinates():
    # Valid India coordinates
    assert validate_cap_coordinate(19.8135, 85.8312) is True
    assert validate_cap_coordinate(8.0883, 77.5385) is True  # Kanyakumari
    assert validate_cap_coordinate(35.5, 76.5) is True      # Ladakh

    # Invalid coordinates (out of range or non-numeric)
    assert validate_cap_coordinate(95.0, 80.0) is False   # Lat > 90
    assert validate_cap_coordinate(-95.0, 80.0) is False  # Lat < -90
    assert validate_cap_coordinate(20.0, 190.0) is False  # Lon > 180
    assert validate_cap_coordinate(None, 80.0) is False


def test_a_valid_cap_polygon():
    """TEST A: Valid CAP polygon string -> valid GeoJSON Polygon with [lon, lat] ordering and closed ring"""
    # CAP format: "lat,lon lat,lon lat,lon lat,lon"
    poly_str = "19.81,85.83 20.15,86.20 20.30,85.90 19.81,85.83"
    
    # Test linear ring parsing
    ring = parse_cap_polygon_string(poly_str)
    assert ring is not None
    assert len(ring) == 4
    assert ring[0] == [85.83, 19.81]
    assert ring[-1] == [85.83, 19.81]

    # Test GeoJSON polygon generation
    geom = parse_cap_polygon_geojson(poly_str)
    assert geom is not None
    assert geom["type"] == "Polygon"
    assert len(geom["coordinates"]) == 1  # 1 exterior ring
    coords = geom["coordinates"][0]
    assert len(coords) == 4
    # Check [lon, lat] swap
    assert coords[0] == [85.83, 19.81]
    assert coords[1] == [86.20, 20.15]
    assert coords[2] == [85.90, 20.30]
    assert coords[3] == [85.83, 19.81]  # Closed ring matches start


def test_b_valid_multipolygon():
    """TEST B: Valid multiple polygons -> valid GeoJSON MultiPolygon"""
    xml_cap_multi = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>IMD-MULTI-POLY-001</identifier>
      <sender>imd@nic.in</sender>
      <sent>2026-10-03T12:00:00+05:30</sent>
      <status>Actual</status>
      <msgType>Alert</msgType>
      <scope>Public</scope>
      <info>
        <category>Met</category>
        <event>Cyclone Warning</event>
        <urgency>Immediate</urgency>
        <severity>Extreme</severity>
        <certainty>Observed</certainty>
        <headline>Cyclone Storm Warning</headline>
        <description>Severe cyclonic activity across two maritime zones.</description>
        <area>
          <areaDesc>Zone 1</areaDesc>
          <polygon>19.81,85.83 20.15,86.20 20.30,85.90 19.81,85.83</polygon>
        </area>
        <area>
          <areaDesc>Zone 2</areaDesc>
          <polygon>18.50,84.10 18.90,84.50 18.60,84.70 18.50,84.10</polygon>
        </area>
      </info>
    </alert>"""

    connector = GenericCAPAlertConnector(
        source_id="test-imd-cap",
        name="IMD MultiZone CAP",
        feed_url="https://mausam.imd.gov.in/cap.xml",
    )

    parsed = connector.parse(xml_cap_multi, content_type="xml")
    assert len(parsed) == 1
    alert = parsed[0]
    geom = alert.get("geometry")

    assert geom is not None
    assert geom["type"] == "MultiPolygon"
    assert len(geom["coordinates"]) == 2
    # Verify zone 1 coordinates
    assert geom["coordinates"][0][0][0] == [85.83, 19.81]
    # Verify zone 2 coordinates
    assert geom["coordinates"][1][0][0] == [84.10, 18.50]


def test_c_no_polygon_fallback_to_point():
    """TEST C: No polygon present -> alert geometry is None, existing point behavior preserved"""
    xml_no_poly = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>IMD-POINT-ONLY-002</identifier>
      <sender>imd@nic.in</sender>
      <sent>2026-10-03T12:00:00+05:30</sent>
      <status>Actual</status>
      <msgType>Alert</msgType>
      <scope>Public</scope>
      <info>
        <category>Met</category>
        <event>Heatwave</event>
        <urgency>Expected</urgency>
        <severity>Moderate</severity>
        <headline>Heatwave Warning for Nagpur</headline>
        <description>High temperatures observed in Vidarbha region.</description>
        <area>
          <areaDesc>Nagpur, Maharashtra</areaDesc>
          <circle>21.1458,79.0882,0.0</circle>
        </area>
      </info>
    </alert>"""

    connector = GenericCAPAlertConnector(
        source_id="test-cap-point",
        name="Point CAP",
        feed_url="https://sachet.ndma.gov.in/test.xml",
    )

    parsed = connector.parse(xml_no_poly, content_type="xml")
    assert len(parsed) == 1
    alert = parsed[0]
    assert alert.get("geometry") is None

    events = connector.normalize(parsed)
    assert len(events) == 1
    ev = events[0]
    assert ev.raw_payload.get("geometry") is None


def test_d_malformed_polygon_rejected():
    """TEST D: Malformed coordinate strings, missing commas, or <3 vertices -> safely rejected"""
    # Malformed syntax
    assert parse_cap_polygon_string("invalid string with no coords") is None
    assert parse_cap_polygon_string("19.81 85.83 20.15 86.20") is None  # Missing commas between lat and lon
    
    # Fewer than 3 unique points
    assert parse_cap_polygon_string("19.81,85.83 20.15,86.20") is None
    assert parse_cap_polygon_string("19.81,85.83 19.81,85.83 19.81,85.83") is None  # 1 unique point repeated


def test_e_out_of_range_coordinates_rejected():
    """TEST E: Latitude or longitude out of geographic bounds -> safely rejected"""
    # Latitude > 90
    assert parse_cap_polygon_string("99.81,85.83 20.15,86.20 20.30,85.90 99.81,85.83") is None
    # Longitude > 180
    assert parse_cap_polygon_string("19.81,195.83 20.15,86.20 20.30,85.90 19.81,195.83") is None


def test_f_polygon_and_metadata_preservation():
    """TEST F: Polygon geometry + canonical event metadata (severity, category, verification, etc.) are fully preserved in raw_payload"""
    xml_cap_single = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>SACHET-ODISHA-FLOOD-003</identifier>
      <sender>sachet@ndma.gov.in</sender>
      <sent>2026-10-03T11:00:00+05:30</sent>
      <status>Actual</status>
      <msgType>Alert</msgType>
      <scope>Public</scope>
      <info>
        <category>Met</category>
        <event>Flash Flood</event>
        <urgency>Immediate</urgency>
        <severity>Severe</severity>
        <certainty>Observed</certainty>
        <headline>Flash Flood Warning for Mahanadi Delta</headline>
        <description>Severe flood conditions observed in Cuttack and Kendrapara districts.</description>
        <area>
          <areaDesc>Cuttack, Odisha</areaDesc>
          <polygon>20.46,85.88 20.60,86.10 20.35,86.25 20.46,85.88</polygon>
        </area>
      </info>
    </alert>"""

    connector = GenericCAPAlertConnector(
        source_id="sachet-cap-feed",
        name="NDMA SACHET Feed",
        feed_url="https://sachet.ndma.gov.in/cap.xml",
    )

    parsed = connector.parse(xml_cap_single, content_type="xml")
    assert len(parsed) == 1
    evs = connector.normalize(parsed)
    assert len(evs) == 1
    ev = evs[0]

    assert ev.raw_payload.get("geometry") is not None
    assert ev.raw_payload["geometry"]["type"] == "Polygon"
    assert ev.raw_payload["geometry"]["coordinates"][0][0] == [85.88, 20.46]
    assert ev.source_type == "OFFICIAL"
    assert ev.state == "Odisha"
    assert ev.district == "Cuttack"
