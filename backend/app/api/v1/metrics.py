"""
Observability metrics endpoint — SkyPulse Phase 6
GET /api/v1/metrics/ws  (ADMIN only)
GET /api/v1/metrics/health  (public, lightweight)
"""
from fastapi import APIRouter, Depends
from app.core.dependencies import require_role

router = APIRouter(prefix="/metrics", tags=["Observability"])


@router.get("/ws")
async def ws_metrics(_: None = Depends(require_role("ADMIN"))):
    """Real-time WebSocket gateway metrics."""
    from app.core.websocket_manager import ws_manager
    return ws_manager.get_stats()


@router.get("/health")
async def system_health():
    """Lightweight health summary for monitoring checks."""
    from app.core.websocket_manager import ws_manager
    stats = ws_manager.get_stats()
    return {
        "status": "ok",
        "websocket": {
            "active_connections": stats["active_connections"],
            "redis_live": stats["redis_live"],
        },
        "kafka": {
            "note": "See /api/health for full status"
        },
    }
