"""
Observability metrics endpoint — SkyPulse Phase 6
GET /api/v1/metrics/ws  (ADMIN only)
GET /api/v1/metrics/health  (public, lightweight)
"""
from fastapi import APIRouter, Depends
from app.core.dependencies import require_role

router = APIRouter(prefix="/metrics", tags=["Observability"])


@router.get("/kpi")
async def kpi_metrics():
    """National-level KPI operational metrics for command center situation rail."""
    from app.db.session import AsyncSessionLocal
    from app.services.weather_intelligence_service import weather_intelligence_service
    async with AsyncSessionLocal() as db:
        stats = await weather_intelligence_service.get_statistics(db=db)
        return {
            "total_events": stats.get("events_total", 0),
            "events_last_24h": stats.get("events_last_24h", 0),
            "events_last_hour": stats.get("events_last_hour", 0),
            "total_reports": stats.get("total_evidence_records", 0),
            "active_severe_alerts": stats.get("active_severe_alerts", 0),
            "categories": stats.get("categories", {}),
            "top_affected_states": stats.get("top_affected_states", []),
            "timestamp": stats.get("timestamp"),
        }


@router.get("/ws")
async def ws_metrics(_: None = Depends(require_role("ADMIN"))):
    """Real-time WebSocket gateway metrics."""
    from app.core.websocket_manager import ws_manager
    return ws_manager.get_stats()


@router.get("/opensearch")
async def opensearch_metrics():
    """Real-time OpenSearch indexing & search metrics telemetry."""
    from ai.opensearch_indexer import opensearch_indexer
    return opensearch_indexer.get_health_status()


@router.get("/neo4j")
async def neo4j_metrics():
    """Real-time Neo4j / DWEG graph projection & query telemetry."""
    from app.db.neo4j_session import get_neo4j_health_status
    return await get_neo4j_health_status()


@router.get("/health")
async def system_health():
    """Lightweight health summary for monitoring checks."""
    from app.core.websocket_manager import ws_manager
    from ai.opensearch_indexer import opensearch_indexer
    from app.db.neo4j_session import get_neo4j_health_status
    stats = ws_manager.get_stats()
    os_health = opensearch_indexer.get_health_status()
    neo_health = await get_neo4j_health_status()
    return {
        "status": "ok",
        "websocket": {
            "active_connections": stats["active_connections"],
            "redis_live": stats["redis_live"],
        },
        "opensearch": {
            "status": os_health["status"],
            "is_live": os_health["is_live"],
            "cluster_status": os_health["cluster_status"],
            "metrics": os_health["metrics"],
        },
        "neo4j": {
            "status": neo_health["status"],
            "is_live": neo_health["is_live"],
            "database": neo_health["database"],
            "metrics": neo_health["metrics"],
        },
        "kafka": {
            "note": "See /api/health for full status"
        },
    }
