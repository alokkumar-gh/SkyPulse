"""
Firebase Cloud Storage Provider for SkyPulse.
Handles binary media uploads (photos, videos, evidence),
time-limited signed URLs, deletion, and telemetry.
"""

import io
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.storage.base import BaseObjectStorageProvider

logger = logging.getLogger("skypulse.storage.firebase")


class FirebaseStorageProvider(BaseObjectStorageProvider):
    """Production Firebase Cloud Storage provider backed by Firebase Admin SDK."""

    def __init__(self):
        self._app = None
        self._bucket = None
        self._is_initialized = False
        self._init_error: Optional[str] = None
        self._last_successful_op: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._last_error_at: Optional[datetime] = None

        # Telemetry counters
        self.upload_attempts: int = 0
        self.successful_uploads: int = 0
        self.failed_uploads: int = 0
        self.bytes_uploaded: int = 0
        self.duplicate_uploads: int = 0
        self.deleted_files: int = 0
        self.firebase_errors: int = 0

    @property
    def provider_name(self) -> str:
        return "FIREBASE"

    def is_configured(self) -> bool:
        """Returns True if Firebase storage is explicitly enabled and configured."""
        if not settings.FIREBASE_STORAGE_ENABLED:
            return False

        has_cert_file = bool(settings.FIREBASE_CREDENTIALS_PATH and os.path.exists(settings.FIREBASE_CREDENTIALS_PATH))
        has_env_creds = bool(settings.FIREBASE_CLIENT_EMAIL and settings.FIREBASE_PRIVATE_KEY)
        has_bucket = bool(settings.FIREBASE_STORAGE_BUCKET)

        return (has_cert_file or has_env_creds) and has_bucket

    def _ensure_client(self) -> bool:
        """Initializes the Firebase Admin app and storage bucket client safely."""
        if self._is_initialized and self._bucket is not None:
            return True

        if not self.is_configured():
            self._init_error = "Firebase Storage is not enabled or credentials/bucket are missing in configuration."
            return False

        try:
            import firebase_admin
            from firebase_admin import credentials, storage

            app_name = "skypulse-firebase-storage"
            try:
                self._app = firebase_admin.get_app(name=app_name)
            except ValueError:
                cred = None
                if settings.FIREBASE_CREDENTIALS_PATH and os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
                    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                elif settings.FIREBASE_CLIENT_EMAIL and settings.FIREBASE_PRIVATE_KEY:
                    private_key = settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n")
                    cert_dict = {
                        "type": "service_account",
                        "project_id": settings.FIREBASE_PROJECT_ID or "skypulse",
                        "private_key": private_key,
                        "client_email": settings.FIREBASE_CLIENT_EMAIL,
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                    cred = credentials.Certificate(cert_dict)
                else:
                    cred = credentials.ApplicationDefault()

                self._app = firebase_admin.initialize_app(
                    cred,
                    {"storageBucket": settings.FIREBASE_STORAGE_BUCKET},
                    name=app_name,
                )

            self._bucket = storage.bucket(name=settings.FIREBASE_STORAGE_BUCKET, app=self._app)
            self._is_initialized = True
            self._init_error = None
            return True

        except Exception as exc:
            self._is_initialized = False
            self._bucket = None
            self._init_error = str(exc)
            self._last_error = f"Firebase initialization failure: {exc}"
            self._last_error_at = datetime.now(timezone.utc)
            self.firebase_errors += 1
            logger.error("Failed to initialize Firebase Admin Storage: %s", exc)
            return False

    async def upload_bytes(
        self,
        data: bytes,
        destination_path: str,
        content_type: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """Uploads binary file to Firebase Cloud Storage bucket."""
        self.upload_attempts += 1
        safe_path = destination_path.lstrip("/")

        if not self._ensure_client():
            self.failed_uploads += 1
            err = self._init_error or "Firebase storage not initialized"
            return False, safe_path, err

        try:
            blob = self._bucket.blob(safe_path)
            if metadata:
                blob.metadata = metadata

            blob.upload_from_string(
                data,
                content_type=content_type,
            )

            self.successful_uploads += 1
            self.bytes_uploaded += len(data)
            self._last_successful_op = datetime.now(timezone.utc)
            logger.info("Uploaded %d bytes to Firebase Storage at '%s'", len(data), safe_path)
            return True, safe_path, None

        except Exception as exc:
            self.failed_uploads += 1
            self.firebase_errors += 1
            self._last_error = str(exc)
            self._last_error_at = datetime.now(timezone.utc)
            logger.error("Firebase upload failed for '%s': %s", safe_path, exc)
            return False, safe_path, str(exc)

    async def get_download_signed_url(
        self,
        storage_path: str,
        expires_in_seconds: int = 3600,
    ) -> Optional[str]:
        """Generates a short-lived v4 signed download URL for private citizen media."""
        if not self._ensure_client():
            return None

        safe_path = storage_path.lstrip("/")
        try:
            blob = self._bucket.blob(safe_path)
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=expires_in_seconds),
                method="GET",
            )
            self._last_successful_op = datetime.now(timezone.utc)
            return signed_url
        except Exception as exc:
            self.firebase_errors += 1
            self._last_error = f"Signed URL generation failed for '{safe_path}': {exc}"
            self._last_error_at = datetime.now(timezone.utc)
            logger.warning("Failed generating Firebase signed URL for '%s': %s", safe_path, exc)
            return None

    async def delete_object(self, storage_path: str) -> bool:
        """Deletes object from Firebase Storage."""
        if not self._ensure_client():
            return False

        safe_path = storage_path.lstrip("/")
        try:
            blob = self._bucket.blob(safe_path)
            if blob.exists():
                blob.delete()
            self.deleted_files += 1
            self._last_successful_op = datetime.now(timezone.utc)
            return True
        except Exception as exc:
            self.firebase_errors += 1
            self._last_error = f"Delete failed for '{safe_path}': {exc}"
            self._last_error_at = datetime.now(timezone.utc)
            logger.error("Failed to delete Firebase object '%s': %s", safe_path, exc)
            return False

    async def check_object_exists(self, storage_path: str) -> bool:
        """Checks if a specified object exists in the Firebase bucket."""
        if not self._ensure_client():
            return False

        safe_path = storage_path.lstrip("/")
        try:
            blob = self._bucket.blob(safe_path)
            return bool(blob.exists())
        except Exception as exc:
            self.firebase_errors += 1
            self._last_error = f"Exists check failed: {exc}"
            self._last_error_at = datetime.now(timezone.utc)
            return False

    async def list_objects(self, prefix: str = "", max_results: int = 1000) -> List[str]:
        """Lists object paths in Firebase storage bucket matching prefix."""
        if not self._ensure_client():
            return []

        try:
            blobs = self._bucket.list_blobs(prefix=prefix.lstrip("/"), max_results=max_results)
            return [b.name for b in blobs]
        except Exception as exc:
            self.firebase_errors += 1
            self._last_error = f"List blobs failed: {exc}"
            self._last_error_at = datetime.now(timezone.utc)
            logger.error("Failed listing Firebase blobs: %s", exc)
            return []

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns structured telemetry counters."""
        return {
            "upload_attempts": self.upload_attempts,
            "successful_uploads": self.successful_uploads,
            "failed_uploads": self.failed_uploads,
            "bytes_uploaded": self.bytes_uploaded,
            "duplicate_uploads": self.duplicate_uploads,
            "deleted_files": self.deleted_files,
            "firebase_errors": self.firebase_errors,
        }

    async def get_health_status(self) -> Dict[str, Any]:
        """Returns connection and configuration diagnostics."""
        configured = self.is_configured()
        connection_status = "NOT_CONFIGURED"

        if configured:
            if self._ensure_client():
                connection_status = "HEALTHY" if not self._last_error else "DEGRADED"
            else:
                connection_status = "ERROR"

        return {
            "enabled": settings.FIREBASE_STORAGE_ENABLED,
            "configured": configured,
            "storage_provider": self.provider_name,
            "storage_bucket": settings.FIREBASE_STORAGE_BUCKET,
            "project_id": settings.FIREBASE_PROJECT_ID,
            "connection_status": connection_status,
            "last_successful_operation": self._last_successful_op,
            "last_error": self._last_error or self._init_error,
            "last_error_at": self._last_error_at,
            "telemetry": self.get_telemetry(),
        }
