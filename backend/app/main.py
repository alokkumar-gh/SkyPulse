from contextlib import asynccontextmanager
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

    # Start Phase 6 real-time gateway (non-blocking; fails gracefully if Kafka/Redis offline)
    try:
        from workers.realtime_gateway import realtime_gateway
        await realtime_gateway.start()
        logger.info("Real-time gateway started")
    except Exception as exc:
        logger.warning("Real-time gateway startup warning: %s (non-fatal)", exc)

    yield

    logger.info("Shutting down SkyPulse application...")
    try:
        from workers.realtime_gateway import realtime_gateway
        await realtime_gateway.stop()
    except Exception:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    description="SkyPulse — National Weather Big Data Analytics Platform",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
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
