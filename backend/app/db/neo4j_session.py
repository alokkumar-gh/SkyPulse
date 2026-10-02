"""Neo4j Client and Schema Initialization for DWEG (Dynamic Weather Evidence Graph)"""

import logging
from typing import Optional
from neo4j import AsyncGraphDatabase, AsyncDriver
from app.core.config import settings

logger = logging.getLogger("skypulse.dweg")

_driver: Optional[AsyncDriver] = None


def get_neo4j_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_lifetime=3600,
        )
    return _driver


async def close_neo4j_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


async def check_neo4j_connection() -> bool:
    """Verify if Neo4j instance is accessible."""
    try:
        driver = get_neo4j_driver()
        async with driver.session() as session:
            result = await session.run("RETURN 1 AS ping")
            record = await result.single()
            return record is not None and record["ping"] == 1
    except Exception as e:
        logger.debug("Neo4j ping failed: %s", e)
        return False


async def initialize_neo4j_schema() -> bool:
    """Initialize uniqueness constraints and indexes for DWEG in Neo4j."""
    constraints = [
        "CREATE CONSTRAINT c_we_id IF NOT EXISTS FOR (e:WeatherEvent) REQUIRE e.id IS UNIQUE",
        "CREATE CONSTRAINT c_wr_id IF NOT EXISTS FOR (r:WeatherReport) REQUIRE r.id IS UNIQUE",
        "CREATE CONSTRAINT c_loc_id IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE",
        "CREATE CONSTRAINT c_src_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE",
        "CREATE INDEX idx_we_category IF NOT EXISTS FOR (e:WeatherEvent) ON (e.category)",
        "CREATE INDEX idx_loc_state IF NOT EXISTS FOR (l:Location) ON (l.state)",
    ]

    try:
        driver = get_neo4j_driver()
        async with driver.session() as session:
            for constraint in constraints:
                await session.run(constraint)
        logger.info("Neo4j DWEG schema and constraints initialized successfully.")
        return True
    except Exception as e:
        logger.warning("Could not initialize Neo4j schema (Neo4j may be offline): %s", e)
        return False

