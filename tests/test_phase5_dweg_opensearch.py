"""
SkyPulse Phase 5 Tests — DWEG (Dynamic Weather Evidence Graph) & OpenSearch
Tests DWEG graph modeling, propagation trajectory detection, heatmap confidence field,
and OpenSearch indexing & multi-criteria search.
"""

import pytest
from datetime import datetime, timezone, timedelta

from ai.dweg_service import DWEGService
from ai.opensearch_indexer import OpenSearchIndexer


@pytest.mark.asyncio
async def test_dweg_node_and_edge_creation():
    """Verify DWEG creates event, report, location, and source nodes with appropriate edges."""
    dweg = DWEGService()

    # 1. Upsert nodes
    evt_node = await dweg.upsert_event_node(
        event_id="evt-kolkata-cyclone-1",
        category="CYCLONE",
        severity=4,
        confidence=0.88,
        status="VERIFIED",
        lat=22.5726,
        lon=88.3639,
        city="Kolkata",
    )
    assert evt_node.id == "evt_evt-kolkata-cyclone-1"
    assert evt_node.properties["category"] == "CYCLONE"

    rep_node = await dweg.upsert_report_node(
        report_id="rep-radar-01",
        source_id="imd_dop_radar",
        source_type="GOVERNMENT_API",
        category="CYCLONE",
        text="Very severe cyclonic storm approaching Kolkata coast",
        confidence=0.92,
        lat=22.5726,
        lon=88.3639,
        city="Kolkata",
    )
    assert rep_node.id == "rep_rep-radar-01"

    # 2. Link Report to Event (SUPPORTS)
    edge = await dweg.link_report_to_event(
        report_id="rep-radar-01",
        event_id="evt-kolkata-cyclone-1",
        corroboration_score=0.95,
    )
    assert edge.relationship == "SUPPORTS"
    assert edge.properties["corroboration_score"] == 0.95

    # 3. Retrieve subgraph
    subgraph = await dweg.get_event_graph("evt-kolkata-cyclone-1")
    assert subgraph["event_id"] == "evt-kolkata-cyclone-1"
    assert subgraph["node_count"] >= 2
    assert subgraph["edge_count"] >= 1


@pytest.mark.asyncio
async def test_dweg_propagation_detection():
    """Verify DWEG detects physical storm propagation from upstream event to adjacent location."""
    dweg = DWEGService()

    t0 = datetime.now(timezone.utc) - timedelta(hours=3)
    # Upstream storm cell in Pune at t0
    await dweg.upsert_event_node(
        event_id="evt-pune-storm",
        category="THUNDERSTORM",
        severity=3,
        confidence=0.85,
        status="VERIFIED",
        lat=18.5204,
        lon=73.8567,
        city="Pune",
    )
    dweg._nodes["evt_evt-pune-storm"].properties["updated_at"] = t0.isoformat()

    # Downstream storm cell in Mumbai (120km northwest, 3 hours later)
    now = datetime.now(timezone.utc)
    prop_res = await dweg.detect_propagation(
        event_id="evt-mumbai-storm",
        category="THUNDERSTORM",
        lat=19.0760,
        lon=72.8777,
        occurred_at=now,
        max_distance_km=180.0,
    )

    assert prop_res.is_propagation is True
    assert prop_res.parent_event_id == "evt-pune-storm"
    assert prop_res.distance_km is not None
    assert 50.0 <= prop_res.distance_km <= 160.0
    assert prop_res.confidence >= 0.50


@pytest.mark.asyncio
async def test_dweg_confidence_field_geojson():
    """Verify compute_confidence_field returns valid GeoJSON FeatureCollection with weighted points."""
    dweg = DWEGService()

    await dweg.upsert_event_node(
        event_id="evt-flood-kochi",
        category="FLOODING",
        severity=3,
        confidence=0.80,
        status="LIKELY",
        lat=9.9312,
        lon=76.2673,
        city="Kochi",
    )
    await dweg.upsert_report_node(
        report_id="rep-k1",
        source_id="citizen-1",
        source_type="CITIZEN",
        category="FLOODING",
        text="Flooding near Marine Drive",
        confidence=0.75,
        lat=9.9816,
        lon=76.2799,
        city="Kochi",
    )
    await dweg.link_report_to_event("rep-k1", "evt-flood-kochi", corroboration_score=0.90)

    geojson = await dweg.compute_confidence_field("evt-flood-kochi")
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) >= 1

    feature = geojson["features"][0]
    assert feature["type"] == "Feature"
    assert "coordinates" in feature["geometry"]
    assert "weight" in feature["properties"]
    assert feature["properties"]["weight"] > 0.0


@pytest.mark.asyncio
async def test_dweg_evidence_chain_narrative():
    """Verify DWEG generates a structured factual narrative of event genesis and corroboration."""
    dweg = DWEGService()

    await dweg.upsert_event_node(
        event_id="evt-heat-nagpur",
        category="HEATWAVE",
        severity=3,
        confidence=0.91,
        status="VERIFIED",
        lat=21.1458,
        lon=79.0882,
        city="Nagpur",
    )
    await dweg.upsert_report_node(
        report_id="rep-nag-1",
        source_id="imd_station",
        source_type="GOVERNMENT_API",
        category="HEATWAVE",
        text="Max temperature 45.2C",
        lat=21.1458,
        lon=79.0882,
        city="Nagpur",
    )
    await dweg.link_report_to_event("rep-nag-1", "evt-heat-nagpur", corroboration_score=1.0)

    res = await dweg.generate_evidence_chain_narrative("evt-heat-nagpur")
    assert res["event_id"] == "evt-heat-nagpur"
    assert "HEATWAVE" in res["narrative"]
    assert "Nagpur" in res["narrative"]
    assert res["evidence_count"] >= 1


@pytest.mark.asyncio
async def test_opensearch_indexer_and_multi_criteria_search():
    """Verify OpenSearchIndexer stores documents and supports multi-field filtering."""
    indexer = OpenSearchIndexer()

    doc1 = {
        "id": "rep-os-1",
        "primary_category": "FLOODING",
        "location_city": "Mumbai",
        "location_state": "Maharashtra",
        "location_lat": 19.0760,
        "location_lon": 72.8777,
        "normalized_text": "Severe waterlogging near Kurla station",
        "verification_status": "VERIFIED",
        "confidence_score": 0.85,
    }
    doc2 = {
        "id": "rep-os-2",
        "primary_category": "HEATWAVE",
        "location_city": "Jaipur",
        "location_state": "Rajasthan",
        "location_lat": 26.9124,
        "location_lon": 75.7873,
        "normalized_text": "Scorching temperatures exceeding 44 degrees in Jaipur",
        "verification_status": "LIKELY",
        "confidence_score": 0.70,
    }

    await indexer.index_report(doc1)
    await indexer.index_report(doc2)

    # Search by category
    flood_results = await indexer.search_reports(category="FLOODING")
    assert len(flood_results) >= 1
    assert any(d["id"] == "rep-os-1" for d in flood_results)

    # Search by city
    jaipur_results = await indexer.search_reports(city="Jaipur")
    assert len(jaipur_results) >= 1
    assert any(d["id"] == "rep-os-2" for d in jaipur_results)

    # Search by text
    text_results = await indexer.search_reports(query_text="waterlogging")
    assert len(text_results) >= 1
    assert text_results[0]["id"] == "rep-os-1"
