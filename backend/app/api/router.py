from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.reports import router as reports_router
from app.api.v1.events import router as events_router
from app.api.v1.verification import router as verification_router
from app.api.v1.sources import router as sources_router
from app.api.v1.locations import router as locations_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.map import router as map_router
from app.api.v1.admin import router as admin_router
from app.api.v1.dweg import router as dweg_router
from app.api.v1.media import router as media_router
from app.api.v1.storage import router as storage_router
from app.api.v1.connectors import (
    connectors_router,
    search_discovery_router,
    news_website_router,
    unified_connectors_router,
)

# Phase 6
from app.api.v1.notifications import router as notifications_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.metrics import router as metrics_router

from app.api.v1.emerging_events import router as emerging_events_router
from app.api.v1.ai import router as ai_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(reports_router)
api_router.include_router(events_router)
api_router.include_router(emerging_events_router)
api_router.include_router(verification_router)
api_router.include_router(sources_router)
api_router.include_router(connectors_router)
api_router.include_router(search_discovery_router)
api_router.include_router(news_website_router)
api_router.include_router(unified_connectors_router)
api_router.include_router(locations_router)
api_router.include_router(analytics_router)
api_router.include_router(map_router)
api_router.include_router(admin_router)
api_router.include_router(dweg_router)
api_router.include_router(media_router)
api_router.include_router(storage_router)
api_router.include_router(ai_router)

# Phase 6
api_router.include_router(notifications_router)
api_router.include_router(alerts_router)
api_router.include_router(metrics_router)

