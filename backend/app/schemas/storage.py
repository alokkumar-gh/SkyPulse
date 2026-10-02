"""
Storage and Media Pydantic schemas for SkyPulse.
Provides structured contracts for Firebase Cloud Storage,
media uploads, signed access URLs, and orphan diagnostics.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class StorageProviderEnum(str, Enum):
    FIREBASE = "FIREBASE"
    MINIO = "MINIO"
    LOCAL = "LOCAL"
    AUTO = "AUTO"


class MediaUploadStatusEnum(str, Enum):
    PENDING = "PENDING"
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    FAILED = "FAILED"
    DELETED = "DELETED"


class MediaDetailResponse(BaseModel):
    id: str
    weather_report_id: Optional[str] = None
    citizen_id: Optional[str] = None
    event_id: Optional[str] = None
    evidence_id: Optional[str] = None
    media_type: str
    storage_provider: str
    storage_key: str
    storage_path: Optional[str] = None
    storage_bucket: str
    original_filename: Optional[str] = None
    safe_filename: Optional[str] = None
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    content_hash: Optional[str] = None
    upload_status: str
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MediaUploadResult(BaseModel):
    media_id: str
    media_type: str
    filename: str
    safe_filename: str
    size_bytes: int
    content_hash: str
    storage_provider: str
    storage_bucket: str
    storage_path: str
    status: str
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_duplicate: bool = False

    model_config = ConfigDict(from_attributes=True)


class AttachMediaRequest(BaseModel):
    media_ids: List[str] = Field(..., min_length=1)


class FirebaseStorageTelemetry(BaseModel):
    upload_attempts: int = 0
    successful_uploads: int = 0
    failed_uploads: int = 0
    bytes_uploaded: int = 0
    duplicate_uploads: int = 0
    deleted_files: int = 0
    firebase_errors: int = 0


class FirebaseStorageStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    storage_provider: str
    storage_bucket: Optional[str] = None
    project_id: Optional[str] = None
    connection_status: str
    last_successful_operation: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    telemetry: FirebaseStorageTelemetry

    model_config = ConfigDict(from_attributes=True)


class OrphanReconciliationReport(BaseModel):
    checked_at: datetime
    storage_provider: str
    orphaned_storage_objects: List[str] = []
    missing_storage_objects: List[str] = []
    metadata_mismatches_count: int = 0
    details: List[Dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)
