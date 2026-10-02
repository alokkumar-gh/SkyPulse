"""
SkyPulse Spatial Adjacency Pre-computation Script — Phase 10
============================================================
Pre-computes spatial adjacency between administrative districts using
PostGIS boundary analysis (ST_Touches / ST_Intersects / distance proximity).
Stores results in PostgreSQL `locations.adjacent_location_ids` and loads
`SPATIALLY_ADJACENT` edges into Neo4j for fast Cypher propagation queries.
"""

import os
import sys
import uuid
import math
import asyncio
import logging
from typing import Dict, List, Tuple
from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.db.session import async_session_factory
from app.models.location import Location
from app.db.neo4j_session import get_neo4j_driver, check_neo4j_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("skypulse.compute_adjacency")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    y = math.sin(dlam) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


async def compute_and_store_adjacency(session: AsyncSession) -> Dict[uuid.UUID, List[uuid.UUID]]:
    """Compute spatial adjacency in PostgreSQL and update adjacent_location_ids."""
    logger.info("Fetching locations from PostgreSQL...")
    res = await session.execute(select(Location))
    locations = res.scalars().all()
    if not locations:
        logger.warning("No locations found in database. Please run seed_locations.py first.")
        return {}

    logger.info("Found %d locations.", len(locations))
    adjacency_map: Dict[uuid.UUID, List[uuid.UUID]] = {loc.id: [] for loc in locations}
    adjacency_details: List[Tuple[Location, Location, float, float]] = []

    # First attempt: PostGIS ST_Touches / ST_Intersects if boundaries exist
    has_postgis = False
    try:
        raw_res = await session.execute(
            text(
                """
                SELECT a.id AS id_a, b.id AS id_b
                FROM locations a, locations b
                WHERE a.id <> b.id
                  AND a.boundary IS NOT NULL
                  AND b.boundary IS NOT NULL
                  AND ST_Touches(a.boundary, b.boundary)
                """
            )
        )
        pairs = raw_res.fetchall()
        if pairs:
            has_postgis = True
            for r_a, r_b in pairs:
                adjacency_map[r_a].append(r_b)
            logger.info("PostGIS ST_Touches identified %d polygon boundary adjacencies.", len(pairs))
    except Exception as exc:
        logger.debug("PostGIS ST_Touches check bypassed: %s", exc)

    # Proximity fallback / enhancement (Centroid distance < 120km)
    if not has_postgis or sum(len(v) for v in adjacency_map.values()) == 0:
        logger.info("Computing centroid distance-based adjacency (threshold <= 120km)...")
        for i in range(len(locations)):
            loc_a = locations[i]
            if loc_a.lat is None or loc_a.lon is None:
                continue
            for j in range(i + 1, len(locations)):
                loc_b = locations[j]
                if loc_b.lat is None or loc_b.lon is None:
                    continue

                dist = haversine_km(loc_a.lat, loc_a.lon, loc_b.lat, loc_b.lon)
                # Adjacent if within 120km
                if dist <= 120.0:
                    adjacency_map[loc_a.id].append(loc_b.id)
                    adjacency_map[loc_b.id].append(loc_a.id)

                    bearing_ab = calculate_bearing(loc_a.lat, loc_a.lon, loc_b.lat, loc_b.lon)
                    bearing_ba = (bearing_ab + 180.0) % 360.0
                    adjacency_details.append((loc_a, loc_b, dist, bearing_ab))
                    adjacency_details.append((loc_b, loc_a, dist, bearing_ba))

    # Persist back to PostgreSQL
    updated = 0
    for loc_id, adj_ids in adjacency_map.items():
        if adj_ids:
            # Deduplicate and sort
            unique_ids = list(dict.fromkeys(adj_ids))
            await session.execute(
                update(Location)
                .where(Location.id == loc_id)
                .values(adjacent_location_ids=unique_ids)
            )
            updated += 1

    await session.commit()
    logger.info("Updated adjacent_location_ids for %d locations in PostgreSQL.", updated)

    # Sync into Neo4j
    await sync_adjacency_to_neo4j(locations, adjacency_details)

    return adjacency_map


async def sync_adjacency_to_neo4j(
    locations: List[Location],
    adjacency_details: List[Tuple[Location, Location, float, float]],
) -> None:
    """Load Location nodes and SPATIALLY_ADJACENT edges into Neo4j."""
    is_live = await check_neo4j_connection()
    if not is_live:
        logger.info("Neo4j offline. Spatial adjacency edges retained in PostgreSQL.")
        return

    logger.info("Syncing spatial adjacency into Neo4j...")
    driver = get_neo4j_driver()
    try:
        async with driver.session() as session:
            # 1. Upsert Location nodes
            for loc in locations:
                node_id = f"loc_{str(loc.id)}"
                name = loc.district or loc.name
                query = """
                MERGE (l:Location {id: $id})
                SET l.location_id = $loc_id,
                    l.name = $name,
                    l.state = $state,
                    l.district = $district,
                    l.lat = $lat,
                    l.lon = $lon
                """
                await session.run(
                    query,
                    id=node_id,
                    loc_id=str(loc.id),
                    name=name,
                    state=loc.state or "",
                    district=loc.district or "",
                    lat=loc.lat,
                    lon=loc.lon,
                )

            # 2. Upsert SPATIALLY_ADJACENT edges
            edge_count = 0
            for loc_a, loc_b, dist, bearing in adjacency_details:
                query = """
                MATCH (a:Location {id: $id_a})
                MATCH (b:Location {id: $id_b})
                MERGE (a)-[r:SPATIALLY_ADJACENT]->(b)
                SET r.distance_km = $dist,
                    r.bearing_deg = $bearing,
                    r.shares_boundary = true
                """
                await session.run(
                    query,
                    id_a=f"loc_{str(loc_a.id)}",
                    id_b=f"loc_{str(loc_b.id)}",
                    dist=round(dist, 2),
                    bearing=round(bearing, 1),
                )
                edge_count += 1

            logger.info("Loaded %d SPATIALLY_ADJACENT edges into Neo4j.", edge_count)
    except Exception as exc:
        logger.warning("Error syncing adjacency to Neo4j: %s", exc)


async def main():
    async with async_session_factory() as session:
        await compute_and_store_adjacency(session)


if __name__ == "__main__":
    asyncio.run(main())
