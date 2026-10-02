"""
Unified Storage Management Service for SkyPulse.
Coordinates Firebase Cloud Storage, MinIO, and Local providers.
Enforces validation, SHA-256 hashing, thumbnail generation, deterministic paths,
signed URLs, and orphan reconciliation diagnostics.
"""

import hashlib
import io
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import MediaType
from app.models.media import Media
from app.schemas.storage import (
    MediaUploadResult,
    FirebaseStorageStatusResponse,
    OrphanReconciliationReport,
)
from app.services.storage.base import BaseObjectStorageProvider
from app.services.storage.firebase_provider import FirebaseStorageProvider
from app.services.storage.minio_provider import MinIOStorageProvider
from app.services.storage.local_fallback_provider import LocalFallbackStorageProvider

logger = logging.getLogger("skypulse.storage")


class StorageService:
    """High-level storage coordinator managing binary evidence and citizen media."""

    def __init__(self):
        self.firebase_provider = FirebaseStorageProvider()
        self.minio_provider = MinIOStorageProvider()
        self.local_provider = LocalFallbackStorageProvider()

    def get_provider(self, provider_name: Optional[str] = None) -> BaseObjectStorageProvider:
        """Resolves the appropriate storage provider based on configuration."""
        name = (provider_name or settings.STORAGE_DEFAULT_PROVIDER).upper()

        if name == "FIREBASE":
            return self.firebase_provider
        if name == "MINIO":
            return self.minio_provider
        if name == "LOCAL":
            return self.local_provider

        # AUTO resolution
        if self.firebase_provider.is_configured():
            return self.firebase_provider
        if self.minio_provider.is_configured() and self.minio_provider._get_client() is not None:
            return self.minio_provider

        return self.local_provider

    @staticmethod
    def calculate_sha256(data: bytes) -> str:
        """Computes deterministic SHA-256 hash for binary content deduplication."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitizes user-provided filename to prevent directory traversal and injection."""
        base = os.path.basename(filename)
        clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", base)
        return clean[:100] if clean else "media_item"

    @staticmethod
    def infer_media_type(mime_type: str) -> str:
        """Infers standard MediaType ('IMAGE', 'VIDEO', 'AUDIO') from MIME type."""
        m = (mime_type or "").lower()
        if m.startswith("video"):
            return MediaType.VIDEO.value
        if m.startswith("audio"):
            return MediaType.AUDIO.value
        return MediaType.IMAGE.value

    def validate_file(self, data: bytes, filename: str, mime_type: str) -> Tuple[bool, Optional[str]]:
        """
        Validates media file size, MIME type, and extension against allowed security policies.
        """
        # Size limit check
        if len(data) > settings.MAX_MEDIA_FILE_SIZE_BYTES:
            max_mb = settings.MAX_MEDIA_FILE_SIZE_BYTES / (1024 * 1024)
            return False, f"File size exceeds maximum permitted limit of {max_mb:.1f} MB."

        if len(data) == 0:
            return False, "Uploaded file is empty (0 bytes)."

        # Extension check
        ext = os.path.splitext(filename.lower())[1]
        if ext not in settings.ALLOWED_MEDIA_EXTENSIONS:
            return False, f"File extension '{ext}' is not permitted. Allowed: {settings.ALLOWED_MEDIA_EXTENSIONS}"

        # MIME type check
        if mime_type.lower() not in [m.lower() for m in settings.ALLOWED_MEDIA_MIME_TYPES]:
            return False, f"MIME type '{mime_type}' is not supported. Allowed: {settings.ALLOWED_MEDIA_MIME_TYPES}"

        return True, None

    @staticmethod
    def build_storage_path(
        media_id: str,
        extension: str,
        citizen_id: Optional[str] = None,
        report_id: Optional[str] = None,
        event_id: Optional[str] = None,
        evidence_id: Optional[str] = None,
        is_thumbnail: bool = False,
    ) -> str:
        """
        Generates deterministic, structured, path-traversal-safe storage paths.
        Structure:
          citizen-reports/{citizen_id}/{report_id}/original/{media_id}.{ext}
          citizen-reports/{citizen_id}/{report_id}/thumbnails/{media_id}.webp
          evidence/{event_id}/{evidence_id}/original/{media_id}.{ext}
        """
        ext = extension.lstrip(".")
        subfolder = "thumbnails" if is_thumbnail else "original"
        filename = f"{media_id}.webp" if is_thumbnail else f"{media_id}.{ext}"

        if event_id and evidence_id:
            return f"evidence/{event_id}/{evidence_id}/{subfolder}/{filename}"

        c_id = citizen_id or "anonymous"
        r_id = report_id or "unlinked"
        return f"citizen-reports/{c_id}/{r_id}/{subfolder}/{filename}"

    @staticmethod
    def generate_image_thumbnail(data: bytes, max_size: Tuple[int, int] = (300, 300)) -> Optional[bytes]:
        """Generates compact WebP thumbnail for image media if Pillow is available."""
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(data))
            img.thumbnail(max_size, Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.ANTIALIAS)

            # Convert RGBA/P to RGB if saving
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if len(img.split()) == 4 else None)
                img = background

            out_io = io.BytesIO()
            img.save(out_io, format="WEBP", quality=80)
            return out_io.getvalue()
        except Exception as exc:
            logger.debug("Thumbnail generation skipped / unavailable: %s", exc)
            return None

    async def upload_file(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        citizen_id: Optional[str] = None,
        report_id: Optional[str] = None,
        event_id: Optional[str] = None,
        evidence_id: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Backward-compatible upload interface returning (storage_key, public_or_signed_url).
        """
        media_id = str(uuid.uuid4())
        ext = os.path.splitext(filename.lower())[1] or ".jpg"
        storage_path = self.build_storage_path(
            media_id=media_id,
            extension=ext,
            citizen_id=citizen_id,
            report_id=report_id,
            event_id=event_id,
            evidence_id=evidence_id,
        )

        provider = self.get_provider(provider_name)
        success, uploaded_path, error = await provider.upload_bytes(
            data=file_bytes,
            destination_path=storage_path,
            content_type=content_type,
            metadata={"original_filename": filename, "media_id": media_id},
        )

        if not success:
            logger.warning("Upload to %s failed: %s, falling back to local storage URL", provider.provider_name, error)

        url = await provider.get_download_signed_url(storage_path) or f"/api/v1/media/static/{storage_path}"
        return storage_path, url

    async def process_and_store_media(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        citizen_id: Optional[str] = None,
        report_id: Optional[str] = None,
        event_id: Optional[str] = None,
        evidence_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
        provider_name: Optional[str] = None,
    ) -> MediaUploadResult:
        """
        Complete media pipeline:
        1. Validate file (size, MIME, extension).
        2. Compute SHA-256 hash.
        3. Check duplicate.
        4. Upload original binary to Cloud Storage (Firebase/MinIO).
        5. Generate & upload thumbnail if image.
        6. Persist metadata to PostgreSQL.
        """
        # 1. Validation
        is_valid, val_error = self.validate_file(file_bytes, filename, content_type)
        if not is_valid:
            raise ValueError(val_error)

        # 2. Content Hash
        content_hash = self.calculate_sha256(file_bytes)
        safe_name = self.sanitize_filename(filename)
        media_type = self.infer_media_type(content_type)
        media_id = str(uuid.uuid4())
        ext = os.path.splitext(safe_name.lower())[1] or ".jpg"

        # 3. Duplicate check in PostgreSQL if DB session provided
        is_dup = False
        if db is not None:
            existing = await db.scalar(select(Media).where(Media.content_hash == content_hash))
            if existing:
                is_dup = True

        # 4. Upload Original File
        provider = self.get_provider(provider_name)
        storage_path = self.build_storage_path(
            media_id=media_id,
            extension=ext,
            citizen_id=citizen_id,
            report_id=report_id,
            event_id=event_id,
            evidence_id=evidence_id,
        )

        success, uploaded_path, error = await provider.upload_bytes(
            data=file_bytes,
            destination_path=storage_path,
            content_type=content_type,
            metadata={
                "original_filename": safe_name,
                "media_id": media_id,
                "content_hash": content_hash,
                "citizen_id": str(citizen_id or ""),
            },
        )

        if not success:
            raise RuntimeError(f"Storage upload failed ({provider.provider_name}): {error}")

        # 5. Generate & Store Thumbnail if IMAGE
        thumbnail_path = None
        if media_type == MediaType.IMAGE.value:
            thumb_bytes = self.generate_image_thumbnail(file_bytes)
            if thumb_bytes:
                t_path = self.build_storage_path(
                    media_id=media_id,
                    extension=".webp",
                    citizen_id=citizen_id,
                    report_id=report_id,
                    event_id=event_id,
                    evidence_id=evidence_id,
                    is_thumbnail=True,
                )
                t_success, _, _ = await provider.upload_bytes(
                    data=thumb_bytes,
                    destination_path=t_path,
                    content_type="image/webp",
                )
                if t_success:
                    thumbnail_path = t_path

        # Obtain signed URLs
        download_url = await provider.get_download_signed_url(storage_path)
        thumbnail_url = await provider.get_download_signed_url(thumbnail_path) if thumbnail_path else None

        # 6. Persist metadata to PostgreSQL if session provided
        if db is not None:
            def _to_uuid(val: Any) -> Optional[uuid.UUID]:
                if not val:
                    return None
                if isinstance(val, uuid.UUID):
                    return val
                try:
                    return uuid.UUID(str(val))
                except Exception:
                    return None

            c_uuid = _to_uuid(citizen_id)
            r_uuid = _to_uuid(report_id)
            e_uuid = _to_uuid(event_id)
            ev_uuid = _to_uuid(evidence_id)

            media_record = Media(
                id=uuid.UUID(media_id),
                weather_report_id=r_uuid,
                citizen_id=c_uuid,
                event_id=e_uuid,
                evidence_id=ev_uuid,
                media_type=media_type,
                storage_provider=provider.provider_name,
                storage_key=storage_path,
                storage_path=storage_path,
                storage_bucket=getattr(settings, f"{provider.provider_name}_STORAGE_BUCKET", "skypulse-media") or "skypulse-media",
                original_filename=filename,
                safe_filename=safe_name,
                file_size_bytes=len(file_bytes),
                mime_type=content_type,
                content_hash=content_hash,
                upload_status="UPLOADED",
                thumbnail_path=thumbnail_path,
            )
            db.add(media_record)
            await db.commit()
            await db.refresh(media_record)

        return MediaUploadResult(
            media_id=media_id,
            media_type=media_type,
            filename=filename,
            safe_filename=safe_name,
            size_bytes=len(file_bytes),
            content_hash=content_hash,
            storage_provider=provider.provider_name,
            storage_bucket=getattr(settings, f"{provider.provider_name}_STORAGE_BUCKET", "skypulse-media") or "skypulse-media",
            storage_path=storage_path,
            status="UPLOADED",
            url=download_url,
            thumbnail_url=thumbnail_url,
            is_duplicate=is_dup,
        )

    async def get_media_access_url(
        self,
        media: Media,
        expires_in_seconds: int = 3600,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Generates fresh signed download URLs for original media and thumbnail.
        """
        provider = self.get_provider(media.storage_provider)
        target_path = media.storage_path or media.storage_key
        url = await provider.get_download_signed_url(target_path, expires_in_seconds=expires_in_seconds)
        thumb_url = None
        if media.thumbnail_path:
            thumb_url = await provider.get_download_signed_url(media.thumbnail_path, expires_in_seconds=expires_in_seconds)
        return url, thumb_url

    async def delete_media_file(self, media: Media, db: Optional[AsyncSession] = None) -> bool:
        """Deletes media file from Cloud Storage and updates status to DELETED."""
        provider = self.get_provider(media.storage_provider)
        target_path = media.storage_path or media.storage_key

        deleted = await provider.delete_object(target_path)
        if media.thumbnail_path:
            await provider.delete_object(media.thumbnail_path)

        if db is not None:
            media.upload_status = "DELETED"
            await db.commit()

        return deleted

    async def get_firebase_status(self) -> FirebaseStorageStatusResponse:
        """Retrieves real health and telemetry from the Firebase Storage provider."""
        status_dict = await self.firebase_provider.get_health_status()
        return FirebaseStorageStatusResponse(
            enabled=status_dict["enabled"],
            configured=status_dict["configured"],
            storage_provider=status_dict["storage_provider"],
            storage_bucket=status_dict["storage_bucket"],
            project_id=status_dict["project_id"],
            connection_status=status_dict["connection_status"],
            last_successful_operation=status_dict["last_successful_operation"],
            last_error=status_dict["last_error"],
            last_error_at=status_dict["last_error_at"],
            telemetry=status_dict["telemetry"],
        )

    async def run_orphan_reconciliation(
        self,
        db: AsyncSession,
        provider_name: Optional[str] = None,
    ) -> OrphanReconciliationReport:
        """
        Performs non-destructive diagnostic check for orphaned storage objects or missing files.
        """
        provider = self.get_provider(provider_name)
        cloud_objects = await provider.list_objects(max_results=2000)

        # Query all DB media records for this provider
        db_records = (
            await db.scalars(
                select(Media).where(
                    Media.storage_provider == provider.provider_name,
                    Media.upload_status != "DELETED",
                )
            )
        ).all()

        db_paths = {r.storage_path or r.storage_key for r in db_records}
        cloud_set = set(cloud_objects)

        orphaned = [p for p in cloud_objects if p not in db_paths and not p.endswith(".webp")]
        missing = [p for p in db_paths if p not in cloud_set]

        return OrphanReconciliationReport(
            checked_at=datetime.now(timezone.utc),
            storage_provider=provider.provider_name,
            orphaned_storage_objects=orphaned,
            missing_storage_objects=missing,
            metadata_mismatches_count=len(orphaned) + len(missing),
            details=[
                {"type": "ORPHANED_IN_STORAGE", "path": o} for o in orphaned[:50]
            ] + [
                {"type": "MISSING_IN_STORAGE", "path": m} for m in missing[:50]
            ],
        )


storage_service = StorageService()
