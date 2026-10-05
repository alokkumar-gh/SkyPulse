# SkyPulse FastAPI Application Entrypoint - National Coverage & Data Truth
from contextlib import asynccontextmanager
import asyncio
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.router import api_router

# Phase 6: WebSocket endpoint
from app.api.v1.ws import router as ws_router

# Setup logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("skypulse")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting SkyPulse application...")
    logger.info("Environment: %s | Demo Mode: %s", settings.APP_ENV, settings.DEMO_MODE)

    # Initialize database schema across PostgreSQL and SQLite
    try:
        import app.models  # Register all models on Base.metadata
        from app.db.base import Base
        from app.db.session import engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if not settings.DATABASE_URL.startswith("sqlite"):
                for col, col_type in [
                    ("observed_at", "TIMESTAMPTZ"),
                    ("ingested_at", "TIMESTAMPTZ"),
                    ("last_seen_at", "TIMESTAMPTZ"),
                    ("expires_at", "TIMESTAMPTZ"),
                    ("lifecycle_status", "VARCHAR(20) DEFAULT 'ACTIVE'"),
                ]:
                    try:
                        await conn.execute(text(f"ALTER TABLE weather_events ADD COLUMN IF NOT EXISTS {col} {col_type};"))
                    except Exception:
                        pass

        if settings.DATABASE_URL.startswith("sqlite"):
            async with engine.begin() as conn:
                def _check_and_add_cols(sync_conn):
                    try:
                        cursor = sync_conn.cursor()
                        existing = [c[1] for c in cursor.execute("PRAGMA table_info(weather_events)").fetchall()]
                        new_cols = [
                            ("observed_at", "DATETIME"),
                            ("ingested_at", "DATETIME"),
                            ("last_seen_at", "DATETIME"),
                            ("expires_at", "DATETIME"),
                            ("lifecycle_status", "VARCHAR(20) DEFAULT 'ACTIVE'"),
                        ]
                        for c_name, c_type in new_cols:
                            if c_name not in existing:
                                cursor.execute(f"ALTER TABLE weather_events ADD COLUMN {c_name} {c_type}")
                    except Exception:
                        pass
                await conn.run_sync(_check_and_add_cols)
        logger.info("Database schema verification and auto-creation completed")
    except Exception as exc:
        logger.warning("Database schema auto-creation notice: %s", exc)


    # Initialize OpenSearch indexes (non-blocking; fails gracefully if OpenSearch offline)
    try:
        from app.services.opensearch_indexer import opensearch_indexer
        if getattr(opensearch_indexer, "is_live", False):
            from app.db.opensearch_indexes import initialize_opensearch_indexes
            initialize_opensearch_indexes()
            logger.info("OpenSearch index verification completed")
        else:
            logger.info("OpenSearch offline; using SQLite/In-Memory fallback for search")
    except Exception as exc:
        logger.warning("OpenSearch index verification notice: %s (non-fatal)", exc)

    # Initialize Neo4j DWEG schema (non-blocking in background)
    try:
        from app.db.neo4j_session import initialize_neo4j_schema
        asyncio.create_task(initialize_neo4j_schema())
        logger.info("Neo4j DWEG schema verification scheduled in background")
    except Exception as exc:
        logger.warning("Neo4j schema verification notice: %s (non-fatal)", exc)

    # Start Phase 6 real-time gateway (non-blocking in background)
    try:
        from workers.realtime_gateway import realtime_gateway
        asyncio.create_task(realtime_gateway.start())
        logger.info("Real-time gateway scheduled in background")
    except Exception as exc:
        logger.warning("Real-time gateway startup warning: %s (non-fatal)", exc)

    # Start Weather Intelligence Auto-Fetch Engine
    try:
        from app.services.auto_fetch_manager import auto_fetch_manager
        auto_fetch_manager.start_background_loop()
        logger.info("Weather Intelligence Auto-Fetch Engine started")
    except Exception as exc:
        logger.warning("Auto-fetch engine startup notice: %s (non-fatal)", exc)

    # Initial routine nationwide meteorological observation refresh
    async def _init_weather_observations():
        try:
            await asyncio.sleep(2)
            from app.db.session import AsyncSessionLocal
            from app.services.district_weather_service import district_weather_service
            async with AsyncSessionLocal() as session:
                logger.info("Triggering initial nationwide district weather observation fetch...")
                await district_weather_service.refresh_all_districts(session)
        except Exception as e:
            logger.warning("Initial district weather observation fetch notice: %s", e)

    asyncio.create_task(_init_weather_observations())

    yield

    logger.info("Shutting down SkyPulse application...")
    try:
        from app.services.auto_fetch_manager import auto_fetch_manager
        auto_fetch_manager.stop_background_loop()
    except Exception:
        pass
    try:
        from workers.realtime_gateway import realtime_gateway
        await realtime_gateway.stop()
    except Exception:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    description="SkyPulse — National Weather Big Data Analytics Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers to guarantee standard error response shape:
# {"error": "CODE", "message": "...", "details": {...}}

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    else:
        content = {
            "error": "HTTP_ERROR",
            "message": str(exc.detail),
            "details": {},
        }
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "")
        errors.append({"field": loc, "message": msg})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid request payload or query parameters",
            "details": {"errors": errors},
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected server error occurred",
            "details": {"type": exc.__class__.__name__} if settings.DEBUG else {},
        },
    )


# Mount API Router
app.include_router(api_router)

# Mount WebSocket Router (Phase 6) — at root, not under /api prefix
app.include_router(ws_router)


# Health checks
@app.get("/health", tags=["Health"])
async def root_health_check() -> JSONResponse:
    return JSONResponse(content={"status": "ok"})


@app.get("/api/health", tags=["Health"])
async def api_health_check() -> JSONResponse:
    return JSONResponse(
        content={
            "status": "ok",
            "app": settings.APP_NAME,
            "version": "1.0.0",
            "environment": settings.APP_ENV,
            "demo_mode": settings.DEMO_MODE,
        }
    )
