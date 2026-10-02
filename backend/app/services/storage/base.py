"""
Abstract Base Class for Object Storage Providers in SkyPulse.
Ensures unified API contracts across Firebase Cloud Storage, MinIO, and Local Fallback.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class BaseObjectStorageProvider(ABC):
    """Abstract interface for binary and evidence media object storage."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the storage provider (e.g. FIREBASE, MINIO, LOCAL)."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the provider is fully configured with credentials."""
        pass

    @abstractmethod
    async def upload_bytes(
        self,
        data: bytes,
        destination_path: str,
        content_type: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Uploads raw binary bytes to cloud object storage.
        Returns: (success, storage_path, error_message)
        """
        pass

    @abstractmethod
    async def get_download_signed_url(
        self,
        storage_path: str,
        expires_in_seconds: int = 3600,
    ) -> Optional[str]:
        """
        Generates a short-lived time-limited signed download URL.
        Returns None if not configured or object does not exist.
        """
        pass

    @abstractmethod
    async def delete_object(self, storage_path: str) -> bool:
        """
        Deletes an object from cloud storage.
        Returns True if deleted or did not exist.
        """
        pass

    @abstractmethod
    async def check_object_exists(self, storage_path: str) -> bool:
        """Checks if a specified object exists in the storage bucket."""
        pass

    @abstractmethod
    async def list_objects(self, prefix: str = "", max_results: int = 1000) -> List[str]:
        """Lists object paths in the bucket matching an optional prefix."""
        pass

    @abstractmethod
    def get_telemetry(self) -> Dict[str, Any]:
        """Returns actual operational telemetry counters for this provider."""
        pass

    @abstractmethod
    async def get_health_status(self) -> Dict[str, Any]:
        """Returns health diagnostics and configuration status."""
        pass
