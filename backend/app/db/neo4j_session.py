"""Neo4j Client and Schema Initialization for DWEG (Dynamic Weather Evidence Graph)"""

import time
import logging
from typing import Optional, Dict, Any
from neo4j import AsyncGraphDatabase, AsyncDriver
from app.core.config import settings

logger = logging.getLogger("skypulse.dweg")

_driver: Optional[AsyncDriver] = None

dweg_metrics: Dict[str, Any] = {
    "nodes_projected_total": 0,
    "edges_projected_total": 0,
    "graph_queries_total": 0,
    "sync_errors_total": 0,
    "fallback_activations_total": 0,
    "last_sync_latency_ms": 0.0,
    "last_query_latency_ms": 0.0,
}


def get_neo4j_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_lifetime=3600,
            connection_timeout=10.0,
        )
    return _driver


async def close_neo4j_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


async def check_neo4j_connection() -> bool:
    """Verify if Neo4j instance is accessible."""
    if not getattr(settings, "NEO4J_ENABLED", True):
        return False
    try:
        driver = get_neo4j_driver()
        async with driver.session(database=getattr(settings, "NEO4J_DATABASE", "neo4j")) as session:
            result = await session.run("RETURN 1 AS ping")
            record = await result.single()
            return record is not None and record["ping"] == 1
    except Exception as e:
        logger.debug("Neo4j ping failed: %s", e)
        return False


async def get_neo4j_health_status() -> Dict[str, Any]:
    """Return comprehensive health telemetry for Neo4j/DWEG."""
    is_live = await check_neo4j_connection()
    status = "ONLINE" if is_live else ("DISABLED" if not getattr(settings, "NEO4J_ENABLED", True) else "FALLBACK")
    server_info = None
    if is_live:
        try:
            driver = get_neo4j_driver()
            info = await driver.get_server_info()
            server_info = {
                "agent": getattr(info, "agent", "Neo4j"),
                "protocol_version": getattr(info, "protocol_version", "5.0"),
            }
        except Exception:
            pass

    return {
        "status": status,
        "is_live": is_live,
        "server_info": server_info,
        "database": getattr(settings, "NEO4J_DATABASE", "neo4j"),
        "metrics": dict(dweg_metrics),
    }


async def initialize_neo4j_schema() -> bool:
    """Initialize uniqueness constraints and indexes for DWEG in Neo4j."""
    if not getattr(settings, "NEO4J_ENABLED", True):
        return False

    constraints = [
        "CREATE CONSTRAINT c_we_id IF NOT EXISTS FOR (e:WeatherEvent) REQUIRE e.id IS UNIQUE",
        "CREATE CONSTRAINT c_wr_id IF NOT EXISTS FOR (r:EvidenceReport) REQUIRE r.id IS UNIQUE",
        "CREATE CONSTRAINT c_loc_id IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE",
        "CREATE CONSTRAINT c_src_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE",
        "CREATE INDEX idx_we_category IF NOT EXISTS FOR (e:WeatherEvent) ON (e.category)",
        "CREATE INDEX idx_loc_state IF NOT EXISTS FOR (l:Location) ON (l.state)",
    ]

    try:
        driver = get_neo4j_driver()
        async with driver.session(database=getattr(settings, "NEO4J_DATABASE", "neo4j")) as session:
            for constraint in constraints:
                await session.run(constraint)
        logger.info("Neo4j DWEG schema and constraints initialized successfully.")
        return True
    except Exception as e:
        logger.warning("Could not initialize Neo4j schema (Neo4j may be offline): %s", e)
        return False

