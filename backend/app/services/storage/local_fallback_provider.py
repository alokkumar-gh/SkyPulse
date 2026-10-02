"""
Local / In-Memory Fallback Storage Provider for SkyPulse.
Provides offline development and test support without external cloud dependencies.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.services.storage.base import BaseObjectStorageProvider

logger = logging.getLogger("skypulse.storage.local")


class LocalFallbackStorageProvider(BaseObjectStorageProvider):
    """In-memory mock storage provider used when neither Firebase nor MinIO is configured."""

    def __init__(self):
        self._store: Dict[str, bytes] = {}
        self._metadata: Dict[str, Dict[str, str]] = {}
        self._last_successful_op: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._last_error_at: Optional[datetime] = None

        self.upload_attempts: int = 0
        self.successful_uploads: int = 0
        self.failed_uploads: int = 0
        self.bytes_uploaded: int = 0
        self.duplicate_uploads: int = 0
        self.deleted_files: int = 0

    @property
    def provider_name(self) -> str:
        return "LOCAL"

    def is_configured(self) -> bool:
        return True

    async def upload_bytes(
        self,
        data: bytes,
        destination_path: str,
        content_type: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        self.upload_attempts += 1
        safe_path = destination_path.lstrip("/")
        self._store[safe_path] = data
        if metadata:
            self._metadata[safe_path] = metadata
        self.successful_uploads += 1
        self.bytes_uploaded += len(data)
        self._last_successful_op = datetime.now(timezone.utc)
        return True, safe_path, None

    async def get_download_signed_url(
        self,
        storage_path: str,
        expires_in_seconds: int = 3600,
    ) -> Optional[str]:
        safe_path = storage_path.lstrip("/")
        if safe_path not in self._store:
            return None
        return f"/api/v1/media/static/{safe_path}"

    async def delete_object(self, storage_path: str) -> bool:
        safe_path = storage_path.lstrip("/")
        if safe_path in self._store:
            del self._store[safe_path]
            self._metadata.pop(safe_path, None)
            self.deleted_files += 1
            self._last_successful_op = datetime.now(timezone.utc)
        return True

    async def check_object_exists(self, storage_path: str) -> bool:
        return storage_path.lstrip("/") in self._store

    async def list_objects(self, prefix: str = "", max_results: int = 1000) -> List[str]:
        p = prefix.lstrip("/")
        return [k for k in self._store.keys() if k.startswith(p)][:max_results]

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            "upload_attempts": self.upload_attempts,
            "successful_uploads": self.successful_uploads,
            "failed_uploads": self.failed_uploads,
            "bytes_uploaded": self.bytes_uploaded,
            "duplicate_uploads": self.duplicate_uploads,
            "deleted_files": self.deleted_files,
            "firebase_errors": 0,
        }

    async def get_health_status(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "configured": True,
            "storage_provider": self.provider_name,
            "storage_bucket": "local-in-memory",
            "connection_status": "HEALTHY",
            "last_successful_operation": self._last_successful_op,
            "last_error": self._last_error,
            "last_error_at": self._last_error_at,
            "telemetry": self.get_telemetry(),
        }
