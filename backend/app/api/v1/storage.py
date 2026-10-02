"""
Storage API endpoints for SkyPulse.
Provides health diagnostics, Firebase status, and orphan reconciliation endpoints.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.storage import (
    FirebaseStorageStatusResponse,
    OrphanReconciliationReport,
)
from app.services.storage_service import storage_service

router = APIRouter(prefix="/storage", tags=["Storage & Object Archives"])


@router.get("/firebase/status", response_model=FirebaseStorageStatusResponse)
async def get_firebase_storage_status(
    current_user: User = Depends(get_current_user),
):
    """
    Returns real-time configuration status, connection health, and operational telemetry
    for Firebase Cloud Storage.
    """
    return await storage_service.get_firebase_status()


@router.get("/status")
async def get_general_storage_status(
    current_user: User = Depends(get_current_user),
):
    """
    Returns aggregated health across all configured storage providers (Firebase, MinIO, Local).
    """
    fb = await storage_service.firebase_provider.get_health_status()
    minio = await storage_service.minio_provider.get_health_status()
    active = storage_service.get_provider()

    return {
        "active_provider": active.provider_name,
        "firebase": fb,
        "minio": minio,
    }


@router.get("/diagnostics/orphans", response_model=OrphanReconciliationReport)
async def get_storage_orphan_diagnostics(
    provider: Optional[str] = None,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Performs non-destructive orphan reconciliation comparing Cloud Storage objects
    against PostgreSQL media metadata records. Restricted to Admin role.
    """
    return await storage_service.run_orphan_reconciliation(db=db, provider_name=provider)
