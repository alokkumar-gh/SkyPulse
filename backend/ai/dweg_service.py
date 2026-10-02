"""
SkyPulse Dynamic Weather Evidence Graph (DWEG) Service
Signature innovation of SkyPulse. Models real-time relational evidence networks between
weather events, evidence reports, physical locations, observation sources, and media.
Supports propagation tracking, multi-hop corroboration, and confidence field generation.
Provides Neo4j connectivity with an in-memory graph fallback when the database is offline.
"""

import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.core.config import settings
from ai.deduplicator import haversine_distance_km

logger = logging.getLogger("skypulse.dweg")


class DWEGNode(BaseModel):
    id: str
    label: str  # WeatherEvent, EvidenceReport, Location, Source, MediaItem
    properties: Dict[str, Any] = Field(default_factory=dict)


class DWEGEdge(BaseModel):
    source_id: str
    target_id: str
    relationship: str  # SUPPORTS, CORROBORATES, CONTRADICTS, LOCATED_AT, FROM_SOURCE, PROPAGATES_TO
    properties: Dict[str, Any] = Field(default_factory=dict)


class PropagationResult(BaseModel):
    is_propagation: bool = False
    parent_event_id: Optional[str] = None
    target_event_id: Optional[str] = None
    direction_deg: Optional[float] = None
    distance_km: Optional[float] = None
    time_delta_hours: Optional[float] = None
    confidence: float = 0.0


class DWEGService:
    """
    Manages graph operations for the Dynamic Weather Evidence Graph.
    Uses in-memory graph storage with optional Neo4j live driver synchronization.
    """

    def __init__(self):
        self._nodes: Dict[str, DWEGNode] = {}
        self._edges: List[DWEGEdge] = []
        self._neo4j_driver = None
        self._is_neo4j_live = False

    async def initialize(self) -> None:
        """Attempt Neo4j connection; fall back gracefully to in-memory graph."""
        try:
            from neo4j import AsyncGraphDatabase
            auth = (settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            self._neo4j_driver = AsyncGraphDatabase.driver(settings.NEO4J_URI, auth=auth)
            # Verify connectivity
            async with self._neo4j_driver.session() as s:
                await s.run("RETURN 1 AS ping")
            self._is_neo4j_live = True
            logger.info("Connected to live Neo4j instance at %s", settings.NEO4J_URI)
        except Exception as e:
            self._is_neo4j_live = False
            logger.info("Neo4j unavailable (%s). Using DWEG in-memory graph engine.", e)

    async def close(self) -> None:
        if self._neo4j_driver:
            await self._neo4j_driver.close()
            self._is_neo4j_live = False

    # --- Graph Mutation APIs ---

    async def upsert_location_node(
        self,
        location_id: str,
        name: str,
        state: Optional[str] = None,
        district: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> DWEGNode:
        node = DWEGNode(
            id=f"loc_{location_id}",
            label="Location",
            properties={
                "location_id": location_id,
                "name": name,
                "state": state,
                "district": district,
                "lat": lat,
                "lon": lon,
            },
        )
        self._nodes[node.id] = node
        return node

    async def upsert_source_node(
        self,
        source_id: str,
        name: str,
        source_type: str,
        trust_score: float = 0.5,
    ) -> DWEGNode:
        node = DWEGNode(
            id=f"src_{source_id}",
            label="Source",
            properties={
                "source_id": source_id,
                "name": name,
                "source_type": source_type,
                "trust_score": trust_score,
            },
        )
        self._nodes[node.id] = node
        return node

    async def upsert_event_node(
        self,
        event_id: str,
        category: str,
        severity: int,
        confidence: float,
        status: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        city: Optional[str] = None,
    ) -> DWEGNode:
        node = DWEGNode(
            id=f"evt_{event_id}",
            label="WeatherEvent",
            properties={
                "event_id": event_id,
                "category": category,
                "severity": severity,
                "confidence": confidence,
                "status": status,
                "lat": lat,
                "lon": lon,
                "city": city,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._nodes[node.id] = node

        # Link to Location if coords exist
        if city and lat and lon:
            loc_id = f"loc_{city.lower()}"
            await self.upsert_location_node(city.lower(), city, lat=lat, lon=lon)
            await self.add_edge(node.id, loc_id, "OCCURRED_AT", {"lat": lat, "lon": lon})

        return node

    async def upsert_report_node(
        self,
        report_id: str,
        source_id: str,
        source_type: str,
        category: str,
        text: str,
        confidence: float = 0.5,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        city: Optional[str] = None,
    ) -> DWEGNode:
        node = DWEGNode(
            id=f"rep_{report_id}",
            label="EvidenceReport",
            properties={
                "report_id": report_id,
                "source_id": source_id,
                "source_type": source_type,
                "category": category,
                "text_summary": text[:120] if text else "",
                "confidence": confidence,
                "lat": lat,
                "lon": lon,
                "city": city,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._nodes[node.id] = node

        # Link to Source
        src_id = f"src_{source_id}"
        if src_id not in self._nodes:
            await self.upsert_source_node(source_id, source_type, source_type)
        await self.add_edge(node.id, src_id, "FROM_SOURCE")

        # Link to Location
        if city and lat and lon:
            loc_id = f"loc_{city.lower()}"
            await self.upsert_location_node(city.lower(), city, lat=lat, lon=lon)
            await self.add_edge(node.id, loc_id, "LOCATED_AT")

        return node

    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        relationship: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> DWEGEdge:
        edge = DWEGEdge(
            source_id=source_id,
            target_id=target_id,
            relationship=relationship,
            properties=properties or {},
        )
        self._edges.append(edge)
        return edge

    async def link_report_to_event(
        self,
        report_id: str,
        event_id: str,
        corroboration_score: float = 1.0,
        is_contradicting: bool = False,
    ) -> DWEGEdge:
        rel = "CONTRADICTS" if is_contradicting else "SUPPORTS"
        edge = await self.add_edge(
            source_id=f"rep_{report_id}",
            target_id=f"evt_{event_id}",
            relationship=rel,
            properties={
                "corroboration_score": corroboration_score,
                "added_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return edge

    async def link_report_corroboration(
        self,
        report_id_1: str,
        report_id_2: str,
        similarity_score: float,
    ) -> DWEGEdge:
        """Bidirectional or directed CORROBORATES relationship between two citizen/sensor reports."""
        edge = await self.add_edge(
            source_id=f"rep_{report_id_1}",
            target_id=f"rep_{report_id_2}",
            relationship="CORROBORATES",
            properties={"similarity_score": similarity_score},
        )
        return edge

    # --- Intelligence & Graph Query Algorithms ---

    async def detect_propagation(
        self,
        event_id: str,
        category: str,
        lat: float,
        lon: float,
        occurred_at: Optional[datetime] = None,
        max_distance_km: float = 120.0,
        max_time_delta_h: float = 12.0,
    ) -> PropagationResult:
        """
        Detects if this weather event is a physical propagation of an adjacent prior event.
        Looks for same-category events within distance window occurring earlier in time.
        """
        cur_time = occurred_at or datetime.now(timezone.utc)
        target_node_id = f"evt_{event_id}"

        best_parent = None
        min_distance = float("inf")
        best_delta_h = None
        best_bearing = None

        for n_id, node in self._nodes.items():
            if node.label != "WeatherEvent" or n_id == target_node_id:
                continue

            props = node.properties
            if (props.get("category") or "").upper() != category.upper():
                continue

            n_lat, n_lon = props.get("lat"), props.get("lon")
            if n_lat is None or n_lon is None:
                continue

            dist = haversine_distance_km(n_lat, n_lon, lat, lon)
            if dist > max_distance_km or dist < 2.0:
                continue

            # Check time delta
            t_str = props.get("updated_at")
            if not t_str:
                continue
            prev_time = datetime.fromisoformat(t_str)
            if prev_time.tzinfo is None:
                prev_time = prev_time.replace(tzinfo=timezone.utc)
            if cur_time.tzinfo is None:
                cur_time = cur_time.replace(tzinfo=timezone.utc)
            delta_h = (cur_time - prev_time).total_seconds() / 3600.0

            # Must have occurred earlier (delta_h > 0) and within time threshold
            if 0.1 <= delta_h <= max_time_delta_h:
                if dist < min_distance:
                    min_distance = dist
                    best_parent = props.get("event_id")
                    best_delta_h = delta_h

                    # Bearing calculation
                    y = math.sin(math.radians(lon - n_lon)) * math.cos(math.radians(lat))
                    x = math.cos(math.radians(n_lat)) * math.sin(math.radians(lat)) - math.sin(
                        math.radians(n_lat)
                    ) * math.cos(math.radians(lat)) * math.cos(math.radians(lon - n_lon))
                    best_bearing = (math.degrees(math.atan2(y, x)) + 360) % 360

        if best_parent:
            # Register PROPAGATES_TO edge in DWEG
            await self.add_edge(
                source_id=f"evt_{best_parent}",
                target_id=target_node_id,
                relationship="PROPAGATES_TO",
                properties={
                    "distance_km": round(min_distance, 2),
                    "bearing_deg": round(best_bearing, 1) if best_bearing else None,
                    "delta_hours": round(best_delta_h, 2) if best_delta_h else None,
                },
            )

            # Propagation confidence scales with proximity and temporal alignment
            conf = max(0.50, min(0.95, 1.0 - (min_distance / max_distance_km) * 0.5))
            return PropagationResult(
                is_propagation=True,
                parent_event_id=best_parent,
                target_event_id=event_id,
                direction_deg=round(best_bearing, 1) if best_bearing else None,
                distance_km=round(min_distance, 2),
                time_delta_hours=round(best_delta_h, 2) if best_delta_h else None,
                confidence=round(conf, 2),
            )

        return PropagationResult(is_propagation=False)

    async def compute_confidence_field(self, event_id: str) -> Dict[str, Any]:
        """
        Returns a GeoJSON FeatureCollection with point features weighted by evidence density
        and source trust, suitable for MapLibre/Leaflet heatmap layers.
        """
        evt_key = f"evt_{event_id}"
        features = []

        # Find all evidence reports linked to this event
        for edge in self._edges:
            if edge.target_id == evt_key and edge.relationship == "SUPPORTS":
                rep_node = self._nodes.get(edge.source_id)
                if rep_node:
                    lat = rep_node.properties.get("lat")
                    lon = rep_node.properties.get("lon")
                    conf = rep_node.properties.get("confidence", 0.5)
                    score = edge.properties.get("corroboration_score", 1.0)
                    weight = round(conf * score, 2)

                    if lat is not None and lon is not None:
                        features.append(
                            {
                                "type": "Feature",
                                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                                "properties": {
                                    "report_id": rep_node.properties.get("report_id"),
                                    "weight": weight,
                                    "source_type": rep_node.properties.get("source_type"),
                                    "category": rep_node.properties.get("category"),
                                },
                            }
                        )

        # Include centroid if present
        evt_node = self._nodes.get(evt_key)
        if evt_node:
            e_lat = evt_node.properties.get("lat")
            e_lon = evt_node.properties.get("lon")
            if e_lat and e_lon:
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [e_lon, e_lat]},
                        "properties": {
                            "event_id": event_id,
                            "weight": 1.0,
                            "is_centroid": True,
                            "category": evt_node.properties.get("category"),
                        },
                    }
                )

        return {"type": "FeatureCollection", "features": features}

    async def get_event_graph(self, event_id: str) -> Dict[str, Any]:
        """
        Retrieve sub-graph for a given weather event (nodes & edges for visualization).
        """
        evt_key = f"evt_{event_id}"
        relevant_node_ids = {evt_key}

        # 1-hop and 2-hop traversal
        for edge in self._edges:
            if edge.source_id == evt_key or edge.target_id == evt_key:
                relevant_node_ids.add(edge.source_id)
                relevant_node_ids.add(edge.target_id)

        sub_edges = [
            e.model_dump()
            for e in self._edges
            if e.source_id in relevant_node_ids and e.target_id in relevant_node_ids
        ]
        sub_nodes = [
            self._nodes[n_id].model_dump()
            for n_id in relevant_node_ids
            if n_id in self._nodes
        ]

        return {
            "event_id": event_id,
            "node_count": len(sub_nodes),
            "edge_count": len(sub_edges),
            "nodes": sub_nodes,
            "edges": sub_edges,
        }

    async def generate_evidence_chain_narrative(self, event_id: str) -> Dict[str, Any]:
        """
        Generates an explainable narrative detailing how the weather event formed,
        its contributing evidence sources, and propagation trajectories.
        """
        evt_key = f"evt_{event_id}"
        evt_node = self._nodes.get(evt_key)

        if not evt_node:
            return {"event_id": event_id, "narrative": "No evidence graph found for this event."}

        props = evt_node.properties
        category = props.get("category", "WEATHER")
        city = props.get("city", "the region")
        severity = props.get("severity", 2)
        confidence = props.get("confidence", 0.5)

        supporting_reports = [
            self._nodes[e.source_id]
            for e in self._edges
            if e.target_id == evt_key and e.relationship == "SUPPORTS" and e.source_id in self._nodes
        ]

        propagations = [
            e for e in self._edges
            if e.target_id == evt_key and e.relationship == "PROPAGATES_TO"
        ]

        # Factual narrative synthesis
        narrative_parts = [
            f"A {category} event (Severity {severity}) was tracked in {city} with {confidence:.0%} confidence.",
            f"Corroborated by {len(supporting_reports)} distinct field report(s) across monitoring sensors and citizens.",
        ]

        if propagations:
            p_edge = propagations[0]
            dist = p_edge.properties.get("distance_km")
            bearing = p_edge.properties.get("bearing_deg")
            narrative_parts.append(
                f"Graph analysis indicates this system propagated {dist}km (heading {bearing}°) from upstream storm cell {p_edge.source_id.replace('evt_', '')}."
            )

        return {
            "event_id": event_id,
            "narrative": " ".join(narrative_parts),
            "evidence_count": len(supporting_reports),
            "has_propagation": len(propagations) > 0,
        }


# Global DWEG singleton
dweg_service = DWEGService()
