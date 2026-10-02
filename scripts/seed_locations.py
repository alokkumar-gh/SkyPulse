"""SkyPulse Location Seeding and Spatial Adjacency Initialization"""

import json
import os
import sys
import uuid
from typing import Dict, List
import asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.db.session import async_session_factory
from app.models.location import Location


async def seed_locations(session: AsyncSession) -> int:
    data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "india_locations.json"))
    if not os.path.exists(data_path):
        print(f"Location data not found at {data_path}")
        return 0

    with open(data_path, "r", encoding="utf-8") as f:
        locations_data = json.load(f)

    print(f"Loaded {len(locations_data)} location definitions.")
    district_to_id: Dict[str, uuid.UUID] = {}
    district_to_adj_names: Dict[str, List[str]] = {}
    inserted_count = 0

    # 1. Insert locations
    for item in locations_data:
        # Check if already exists
        stmt = select(Location).where(
            Location.name == item["name"],
            Location.state == item["state"]
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        pt = Point(item["lon"], item["lat"])
        geom = from_shape(pt, srid=4326)

        if not existing:
            loc = Location(
                id=uuid.uuid4(),
                name=item["name"],
                level=item["level"],
                state=item["state"],
                district=item["district"],
                country="IN",
                lat=item["lat"],
                lon=item["lon"],
                centroid=geom,
                adjacent_location_ids=[],
            )
            session.add(loc)
            district_to_id[item["district"]] = loc.id
            district_to_id[item["name"]] = loc.id
            district_to_adj_names[str(loc.id)] = item.get("adjacent_districts", [])
            inserted_count += 1
        else:
            district_to_id[item["district"]] = existing.id
            district_to_id[item["name"]] = existing.id
            district_to_adj_names[str(existing.id)] = item.get("adjacent_districts", [])

    await session.commit()
    print(f"Inserted {inserted_count} new location entities.")

    # 2. Update adjacent_location_ids
    for loc_id_str, adj_names in district_to_adj_names.items():
        loc_uuid = uuid.UUID(loc_id_str)
        adj_ids = []
        for name in adj_names:
            if name in district_to_id:
                adj_ids.append(district_to_id[name])

        if adj_ids:
            stmt = (
                update(Location)
                .where(Location.id == loc_uuid)
                .values(adjacent_location_ids=adj_ids)
            )
            await session.execute(stmt)

    await session.commit()
    print("Pre-computed spatial adjacency lists linked successfully.")
    return len(locations_data)


async def main():
    async with async_session_factory() as session:
        await seed_locations(session)


if __name__ == "__main__":
    asyncio.run(main())
