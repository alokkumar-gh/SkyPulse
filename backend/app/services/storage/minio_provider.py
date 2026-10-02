"""
MinIO / S3 Object Storage Provider for SkyPulse.
Provides secondary object storage support when MinIO is enabled.
"""

import io
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.storage.base import BaseObjectStorageProvider

logger = logging.getLogger("skypulse.storage.minio")


class MinIOStorageProvider(BaseObjectStorageProvider):
    """MinIO S3-compatible object storage provider."""

    def __init__(self):
        self._client = None
        self._connected = False
        self._last_successful_op: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._last_error_at: Optional[datetime] = None

        self.upload_attempts: int = 0
        self.successful_uploads: int = 0
        self.failed_uploads: int = 0
        self.bytes_uploaded: int = 0
        self.duplicate_uploads: int = 0
        self.deleted_files: int = 0
        self.minio_errors: int = 0

    @property
    def provider_name(self) -> str:
        return "MINIO"

    def is_configured(self) -> bool:
        return bool(settings.MINIO_ENDPOINT and settings.MINIO_ACCESS_KEY and settings.MINIO_SECRET_KEY)

    def _get_client(self):
        if self._client is None and self.is_configured():
            try:
                from minio import Minio
                self._client = Minio(
                    settings.MINIO_ENDPOINT,
                    access_key=settings.MINIO_ACCESS_KEY,
                    secret_key=settings.MINIO_SECRET_KEY,
                    secure=settings.MINIO_SECURE,
                )
                self._connected = True
            except Exception as e:
                self._last_error = str(e)
                self._last_error_at = datetime.now(timezone.utc)
                self.minio_errors += 1
                logger.debug("MinIO client initialization failed: %s", e)
                self._client = None
                self._connected = False
        return self._client

    async def upload_bytes(
        self,
        data: bytes,
        destination_path: str,
        content_type: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        self.upload_attempts += 1
        client = self._get_client()
        safe_path = destination_path.lstrip("/")

        if not client:
            self.failed_uploads += 1
            return False, safe_path, "MinIO client not available"

        try:
            if not client.bucket_exists(settings.MINIO_BUCKET_NAME):
                client.make_bucket(settings.MINIO_BUCKET_NAME)

            client.put_object(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=safe_path,
                data=io.BytesIO(data),
                length=len(data),
                content_type=content_type,
                metadata=metadata,
            )
            self.successful_uploads += 1
            self.bytes_uploaded += len(data)
            self._last_successful_op = datetime.now(timezone.utc)
            return True, safe_path, None
        except Exception as exc:
            self.failed_uploads += 1
            self.minio_errors += 1
            self._last_error = str(exc)
            self._last_error_at = datetime.now(timezone.utc)
            return False, safe_path, str(exc)

    async def get_download_signed_url(
        self,
        storage_path: str,
        expires_in_seconds: int = 3600,
    ) -> Optional[str]:
        client = self._get_client()
        safe_path = storage_path.lstrip("/")
        if not client:
            return f"/api/v1/media/static/{safe_path}"

        try:
            return client.presigned_get_object(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=safe_path,
                expires=timedelta(seconds=expires_in_seconds),
            )
        except Exception as exc:
            logger.warning("MinIO presigned GET failed: %s", exc)
            return f"/api/v1/media/static/{safe_path}"

    async def delete_object(self, storage_path: str) -> bool:
        client = self._get_client()
        safe_path = storage_path.lstrip("/")
        if not client:
            return False
        try:
            client.remove_object(settings.MINIO_BUCKET_NAME, safe_path)
            self.deleted_files += 1
            return True
        except Exception as exc:
            self.minio_errors += 1
            self._last_error = str(exc)
            return False

    async def check_object_exists(self, storage_path: str) -> bool:
        client = self._get_client()
        safe_path = storage_path.lstrip("/")
        if not client:
            return False
        try:
            client.stat_object(settings.MINIO_BUCKET_NAME, safe_path)
            return True
        except Exception:
            return False

    async def list_objects(self, prefix: str = "", max_results: int = 1000) -> List[str]:
        client = self._get_client()
        if not client:
            return []
        try:
            objects = client.list_objects(settings.MINIO_BUCKET_NAME, prefix=prefix.lstrip("/"), recursive=True)
            return [o.object_name for o in objects][:max_results]
        except Exception as exc:
            logger.error("MinIO list_objects error: %s", exc)
            return []

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            "upload_attempts": self.upload_attempts,
            "successful_uploads": self.successful_uploads,
            "failed_uploads": self.failed_uploads,
            "bytes_uploaded": self.bytes_uploaded,
            "duplicate_uploads": self.duplicate_uploads,
            "deleted_files": self.deleted_files,
            "minio_errors": self.minio_errors,
        }

    async def get_health_status(self) -> Dict[str, Any]:
        configured = self.is_configured()
        status = "NOT_CONFIGURED"
        if configured:
            client = self._get_client()
            status = "HEALTHY" if client else "ERROR"

        return {
            "enabled": configured,
            "configured": configured,
            "storage_provider": self.provider_name,
            "storage_bucket": settings.MINIO_BUCKET_NAME,
            "connection_status": status,
            "last_successful_operation": self._last_successful_op,
            "last_error": self._last_error,
            "last_error_at": self._last_error_at,
            "telemetry": self.get_telemetry(),
        }
