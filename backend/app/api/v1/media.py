"""
Media & Evidence API endpoints for SkyPulse.
Handles citizen media uploads to Firebase Cloud Storage,
metadata tracking in PostgreSQL, signed access URLs, and secure deletion.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_optional_current_user
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.media import Media
from app.models.user import User
from app.schemas.storage import MediaDetailResponse, MediaUploadResult
from app.services.storage_service import storage_service

router = APIRouter(prefix="/media", tags=["Media & Uploads"])


@router.post("/upload", response_model=MediaUploadResult, status_code=status.HTTP_201_CREATED)
async def upload_media_file(
    file: UploadFile = File(...),
    report_id: Optional[str] = Form(None),
    event_id: Optional[str] = Form(None),
    evidence_id: Optional[str] = Form(None),
    user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload photo/video evidence accompanying a weather report or event.
    Stores binary file in Firebase Cloud Storage (or active provider) and
    persists structured metadata with SHA-256 content hash in PostgreSQL.
    """
    content = await file.read()
    filename = file.filename or "media_upload.jpg"
    content_type = file.content_type or "image/jpeg"
    citizen_id = str(user.id) if user else None

    try:
        result = await storage_service.process_and_store_media(
            file_bytes=content,
            filename=filename,
            content_type=content_type,
            citizen_id=citizen_id,
            report_id=report_id,
            event_id=event_id,
            evidence_id=evidence_id,
            db=db,
        )
        return result
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_FAILED", "message": str(val_err)},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "UPLOAD_FAILED", "message": str(exc)},
        )


@router.get("/{media_id}", response_model=MediaDetailResponse)
async def get_media_detail(
    media_id: str,
    user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves metadata and fresh short-lived signed access URL for a media item.
    Enforces authorization: Citizens can only access their own media or unlinked media,
    while Analysts, Admins, and Government roles can access all evidence.
    """
    try:
        m_uuid = uuid.UUID(media_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_UUID", "message": "Invalid media UUID format."},
        )

    media = await db.scalar(select(Media).where(Media.id == m_uuid, Media.upload_status != "DELETED"))
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "MEDIA_NOT_FOUND", "message": f"Media with ID '{media_id}' not found."},
        )

    # RBAC & Ownership checks
    if media.citizen_id:
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "AUTHENTICATION_REQUIRED", "message": "Authentication required to access private citizen media."},
            )
        if user.role == UserRole.CITIZEN.value and media.citizen_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "You are not authorized to access this citizen media item."},
            )

    url, thumb_url = await storage_service.get_media_access_url(media)

    return MediaDetailResponse(
        id=str(media.id),
        weather_report_id=str(media.weather_report_id) if media.weather_report_id else None,
        citizen_id=str(media.citizen_id) if media.citizen_id else None,
        event_id=str(media.event_id) if media.event_id else None,
        evidence_id=str(media.evidence_id) if media.evidence_id else None,
        media_type=media.media_type,
        storage_provider=media.storage_provider,
        storage_key=media.storage_key,
        storage_path=media.storage_path,
        storage_bucket=media.storage_bucket,
        original_filename=media.original_filename,
        safe_filename=media.safe_filename,
        file_size_bytes=media.file_size_bytes,
        mime_type=media.mime_type,
        content_hash=media.content_hash,
        upload_status=media.upload_status,
        url=url,
        thumbnail_url=thumb_url,
        uploaded_at=media.uploaded_at,
    )


@router.delete("/{media_id}")
async def delete_media_item(
    media_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deletes media file from Cloud Storage and marks status as DELETED in PostgreSQL.
    Permitted for the uploading Citizen or an Admin.
    """
    try:
        m_uuid = uuid.UUID(media_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_UUID", "message": "Invalid media UUID format."},
        )

    media = await db.scalar(select(Media).where(Media.id == m_uuid, Media.upload_status != "DELETED"))
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "MEDIA_NOT_FOUND", "message": f"Media with ID '{media_id}' not found."},
        )

    # Ownership / Admin check
    is_owner = media.citizen_id == user.id
    is_admin = user.role in (UserRole.ADMIN.value, UserRole.ANALYST.value)
    if not (is_owner or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "message": "You do not have permission to delete this media item."},
        )

    await storage_service.delete_media_file(media=media, db=db)

    return {
        "status": "SUCCESS",
        "media_id": media_id,
        "message": "Media successfully deleted from storage and marked DELETED.",
    }


@router.get("/static/{path:path}")
async def get_static_media(path: str):
    """Static placeholder / mock endpoint for local development."""
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="150" viewBox="0 0 200 150">
      <rect width="200" height="150" fill="#1e293b"/>
      <text x="100" y="80" fill="#94a3b8" font-family="sans-serif" font-size="14" text-anchor="middle">SkyPulse Media</text>
    </svg>"""
    return Response(content=svg, media_type="image/svg+xml")
