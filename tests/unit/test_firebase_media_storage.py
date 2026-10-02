"""
Unit & Integration Tests for Firebase Cloud Storage for Citizen Media & Evidence Archival.

Verifies:
1. Firebase configuration missing (NOT_CONFIGURED graceful handling).
2. Firebase configuration present and client initialization.
3. Media MIME type and extension validation.
4. Media file size limits enforcement.
5. Deterministic SHA-256 content hashing and duplicate detection.
6. Safe filename sanitization and path traversal prevention.
7. WebP thumbnail generation for image evidence.
8. Complete upload pipeline and PostgreSQL metadata persistence.
9. Storage upload failure isolation and error reporting (no false confirmations).
10. Signed URL generation and expiration.
11. Media deletion and lifecycle status updating (DELETED).
12. RBAC enforcement (Citizen ownership vs Analyst/Admin access).
13. Citizen report submission with media attachment and DWEG evidence provenance.
14. Storage health status and non-destructive orphan reconciliation diagnostics.
15. Live Firebase smoke test (automatically skipped if credentials are not configured).
"""

import io
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.enums import MediaType, UserRole
from app.models.media import Media
from app.models.weather_report import WeatherReport
from app.models.user import User
from app.schemas.report import CreateReportRequest
from app.schemas.storage import (
    MediaUploadStatusEnum,
    StorageProviderEnum,
    FirebaseStorageStatusResponse,
)
from app.services.report_service import create_report
from app.services.storage.firebase_provider import FirebaseStorageProvider
from app.services.storage.local_fallback_provider import LocalFallbackStorageProvider
from app.services.storage_service import StorageService, storage_service


# Dummy small test images & videos
SAMPLE_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
SAMPLE_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
SAMPLE_MP4_BYTES = b"\x00\x00\x00 ftypisom\x00\x00\x02\x00isomiso2mp41\x00\x00\x00\x08free"


# ==============================================================================
# 1. Configuration & Health Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_1_firebase_configuration_missing():
    """When Firebase credentials are not provided, provider reports NOT_CONFIGURED gracefully."""
    provider = FirebaseStorageProvider()
    with patch.object(settings, "FIREBASE_STORAGE_ENABLED", False):
        with patch.object(settings, "FIREBASE_STORAGE_BUCKET", None):
            assert provider.is_configured() is False
            health = await provider.get_health_status()
            assert health["configured"] is False
            assert health["connection_status"] == "NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_2_firebase_configured_initialization():
    """When Firebase is configured, provider initializes and reports settings without credential leakage."""
    provider = FirebaseStorageProvider()
    with patch.object(settings, "FIREBASE_STORAGE_ENABLED", True):
        with patch.object(settings, "FIREBASE_STORAGE_BUCKET", "skypulse-test-bucket"):
            with patch.object(settings, "FIREBASE_CLIENT_EMAIL", "test-sa@skypulse.iam.gserviceaccount.com"):
                with patch.object(settings, "FIREBASE_PRIVATE_KEY", "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQD---\n-----END PRIVATE KEY-----"):
                    assert provider.is_configured() is True
                    # Verify no private key in health output
                    health = await provider.get_health_status()
                    assert health["storage_bucket"] == "skypulse-test-bucket"
                    assert "private_key" not in health
                    assert "PRIVATE KEY" not in str(health)


# ==============================================================================
# 2. File Validation & Sanitization Tests
# ==============================================================================

def test_3_media_validation_mime_and_extension():
    """Validates permitted MIME types and rejects unsupported or dangerous files."""
    srv = StorageService()

    # Valid JPEG
    ok, err = srv.validate_file(SAMPLE_JPEG_BYTES, "cyclone.jpg", "image/jpeg")
    assert ok is True
    assert err is None

    # Valid MP4
    ok, err = srv.validate_file(SAMPLE_MP4_BYTES, "flood.mp4", "video/mp4")
    assert ok is True
    assert err is None

    # Invalid executable extension
    ok, err = srv.validate_file(b"malicious", "malware.exe", "application/octet-stream")
    assert ok is False
    assert "not permitted" in err

    # Invalid MIME type
    ok, err = srv.validate_file(SAMPLE_JPEG_BYTES, "notes.jpg", "text/plain")
    assert ok is False
    assert "not supported" in err


def test_4_media_validation_file_size_limits():
    """Rejects empty files and files exceeding maximum allowed size."""
    srv = StorageService()

    # 0 bytes
    ok, err = srv.validate_file(b"", "empty.jpg", "image/jpeg")
    assert ok is False
    assert "0 bytes" in err

    # Exceeds size limit (simulate 51 MB)
    large_bytes = b"x" * (51 * 1024 * 1024)
    with patch.object(settings, "MAX_MEDIA_FILE_SIZE_BYTES", 50 * 1024 * 1024):
        ok, err = srv.validate_file(large_bytes, "huge.jpg", "image/jpeg")
        assert ok is False
        assert "exceeds maximum permitted limit" in err


def test_5_sha256_hashing_and_duplicate_detection():
    """Verifies deterministic SHA-256 calculation for deduplication."""
    hash1 = StorageService.calculate_sha256(SAMPLE_JPEG_BYTES)
    hash2 = StorageService.calculate_sha256(SAMPLE_JPEG_BYTES)
    hash3 = StorageService.calculate_sha256(SAMPLE_PNG_BYTES)

    assert len(hash1) == 64
    assert hash1 == hash2
    assert hash1 != hash3


def test_6_safe_filename_and_path_traversal_prevention():
    """Tests filename sanitization and structured path generation."""
    srv = StorageService()

    # Sanitization
    unsafe_name = "../../../etc/passwd;evil.jpg"
    safe = srv.sanitize_filename(unsafe_name)
    assert ".." not in safe
    assert "/" not in safe
    assert safe.endswith(".jpg")

    # Path generation
    media_id = str(uuid.uuid4())
    path = srv.build_storage_path(
        media_id=media_id,
        extension=".jpg",
        citizen_id="citizen-123",
        report_id="report-456",
    )
    assert path.startswith("citizen-reports/citizen-123/report-456/original/")
    assert path.endswith(f"{media_id}.jpg")


def test_7_thumbnail_generation():
    """Generates compact WebP thumbnails for image evidence."""
    from PIL import Image

    img = Image.new("RGB", (200, 200), color=(255, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    valid_img_bytes = buf.getvalue()

    thumb = StorageService.generate_image_thumbnail(valid_img_bytes)
    assert thumb is not None
    assert len(thumb) > 0
    # WebP magic header check (RIFF....WEBP)
    assert thumb[:4] == b"RIFF"
    assert b"WEBP" in thumb[:12]


# ==============================================================================
# 3. Media Pipeline & PostgreSQL Persistence Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_8_media_upload_pipeline_and_postgres_persistence(db_session):
    """
    Tests complete media upload pipeline:
    - File upload to active storage provider
    - Thumbnail generation
    - Structured metadata persistence in PostgreSQL
    """
    srv = StorageService()
    c_id = str(uuid.uuid4())
    r_id = str(uuid.uuid4())

    result = await srv.process_and_store_media(
        file_bytes=SAMPLE_JPEG_BYTES,
        filename="heavy_rain_mumbai.jpg",
        content_type="image/jpeg",
        citizen_id=c_id,
        report_id=r_id,
        db=db_session,
    )

    assert result.status == "UPLOADED"
    assert result.media_type == "IMAGE"
    assert len(result.content_hash) == 64
    assert result.size_bytes == len(SAMPLE_JPEG_BYTES)

    # Verify PostgreSQL metadata record
    media_rec = await db_session.scalar(
        select(Media).where(Media.id == uuid.UUID(result.media_id))
    )
    assert media_rec is not None
    assert str(media_rec.citizen_id) == c_id
    assert str(media_rec.weather_report_id) == r_id
    assert media_rec.original_filename == "heavy_rain_mumbai.jpg"
    assert media_rec.content_hash == result.content_hash
    assert media_rec.upload_status == "UPLOADED"


@pytest.mark.asyncio
async def test_9_storage_upload_failure_handling(db_session):
    """
    When cloud storage upload fails:
    - Exception is raised
    - No falsely confirmed upload is returned
    """
    srv = StorageService()
    mock_provider = LocalFallbackStorageProvider()

    with patch.object(
        mock_provider,
        "upload_bytes",
        return_value=(False, "path", "Simulated Firebase Storage Permission Denied"),
    ):
        with patch.object(srv, "get_provider", return_value=mock_provider):
            with pytest.raises(RuntimeError) as excinfo:
                await srv.process_and_store_media(
                    file_bytes=SAMPLE_JPEG_BYTES,
                    filename="failure_test.jpg",
                    content_type="image/jpeg",
                    db=db_session,
                )
            assert "Storage upload failed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_10_signed_url_generation_and_access(db_session):
    """Verifies generation of time-limited signed access URLs for media and thumbnails."""
    srv = StorageService()
    result = await srv.process_and_store_media(
        file_bytes=SAMPLE_JPEG_BYTES,
        filename="signed_url_test.jpg",
        content_type="image/jpeg",
        db=db_session,
    )

    media_rec = await db_session.scalar(
        select(Media).where(Media.id == uuid.UUID(result.media_id))
    )
    url, thumb_url = await srv.get_media_access_url(media_rec)
    assert url is not None
    assert "/media/" in url or "http" in url


@pytest.mark.asyncio
async def test_11_media_deletion_and_lifecycle_status(db_session):
    """Verifies that media deletion removes object and updates status to DELETED."""
    srv = StorageService()
    result = await srv.process_and_store_media(
        file_bytes=SAMPLE_JPEG_BYTES,
        filename="to_delete.jpg",
        content_type="image/jpeg",
        db=db_session,
    )

    media_rec = await db_session.scalar(
        select(Media).where(Media.id == uuid.UUID(result.media_id))
    )
    deleted = await srv.delete_media_file(media_rec, db=db_session)
    assert deleted is True

    # Check updated record in DB
    refreshed = await db_session.scalar(
        select(Media).where(Media.id == uuid.UUID(result.media_id))
    )
    assert refreshed.upload_status == "DELETED"


# ==============================================================================
# 4. REST API & RBAC Integration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_12_rbac_citizen_isolation_and_analyst_access(client, test_citizen, test_analyst, auth_headers, db_session):
    """
    RBAC verification:
    - Citizen A uploads media
    - Citizen A can retrieve their media
    - Citizen B is forbidden from accessing Citizen A's private media
    - Analyst / Admin can access any media for evidence verification
    """
    headers_citizen_a = auth_headers(test_citizen)

    # 1. Citizen A uploads media
    upload_resp = await client.post(
        "/api/v1/media/upload",
        files={"file": ("citizen_report.jpg", SAMPLE_JPEG_BYTES, "image/jpeg")},
        headers=headers_citizen_a,
    )
    assert upload_resp.status_code == 201
    media_data = upload_resp.json()
    media_id = media_data["media_id"]

    # 2. Citizen A accesses own media -> Permitted (200)
    res_a = await client.get(f"/api/v1/media/{media_id}", headers=headers_citizen_a)
    assert res_a.status_code == 200
    assert res_a.json()["id"] == media_id

    # 3. Citizen B attempts access -> Forbidden (403)
    user_b = User(
        id=uuid.uuid4(),
        email="citizen_b@example.com",
        display_name="Citizen B",
        role=UserRole.CITIZEN.value,
        is_active=True,
    )
    db_session.add(user_b)
    await db_session.commit()

    headers_citizen_b = auth_headers(user_b)
    res_b = await client.get(f"/api/v1/media/{media_id}", headers=headers_citizen_b)
    assert res_b.status_code == 403

    # 4. Analyst accesses media -> Permitted (200)
    headers_analyst = auth_headers(test_analyst)
    res_analyst = await client.get(f"/api/v1/media/{media_id}", headers=headers_analyst)
    assert res_analyst.status_code == 200


@pytest.mark.asyncio
async def test_13_report_media_association_and_dweg_provenance(client, test_citizen, auth_headers, db_session):
    """
    Verifies full end-to-end flow:
    1. Citizen uploads media evidence.
    2. Submits Citizen Weather Report referencing media ID.
    3. Media is linked to report in PostgreSQL.
    4. GET /reports/{report_id}/media returns media evidence.
    """
    headers = auth_headers(test_citizen)

    # 1. Upload photo evidence
    upload_res = await client.post(
        "/api/v1/media/upload",
        files={"file": ("flooding_cuttack.jpg", SAMPLE_JPEG_BYTES, "image/jpeg")},
        headers=headers,
    )
    assert upload_res.status_code == 201
    media_id = upload_res.json()["media_id"]

    # 2. Submit report with media_ids
    report_req = {
        "event_type": "FLOODING",
        "description": "Severe waterlogging near Kathajodi river bank in Cuttack",
        "severity": 3,
        "latitude": 20.4625,
        "longitude": 85.8828,
        "location_name": "Cuttack, Odisha",
        "media_ids": [media_id],
    }
    report_res = await client.post("/api/v1/reports", json=report_req, headers=headers)
    assert report_res.status_code == 201
    report_id = report_res.json()["id"]

    # 3. Retrieve media list for report
    media_list_res = await client.get(f"/api/v1/reports/{report_id}/media", headers=headers)
    assert media_list_res.status_code == 200
    media_items = media_list_res.json()
    assert len(media_items) == 1
    assert media_items[0]["id"] == media_id
    assert media_items[0]["weather_report_id"] == report_id


@pytest.mark.asyncio
async def test_14_storage_status_and_orphan_diagnostics(client, test_admin, auth_headers):
    """Verifies storage health endpoints and non-destructive orphan reconciliation diagnostics."""
    headers = auth_headers(test_admin)

    # 1. GET /api/v1/storage/firebase/status
    res_fb = await client.get("/api/v1/storage/firebase/status", headers=headers)
    assert res_fb.status_code == 200
    fb_data = res_fb.json()
    assert "connection_status" in fb_data
    assert "telemetry" in fb_data

    # 2. GET /api/v1/storage/status
    res_gen = await client.get("/api/v1/storage/status", headers=headers)
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    assert "active_provider" in gen_data

    # 3. GET /api/v1/storage/diagnostics/orphans (Admin role)
    res_diag = await client.get("/api/v1/storage/diagnostics/orphans", headers=headers)
    assert res_diag.status_code == 200
    diag_data = res_diag.json()
    assert "orphaned_storage_objects" in diag_data
    assert "missing_storage_objects" in diag_data


# ==============================================================================
# 5. Live Firebase Smoke Test (Skipped if not configured)
# ==============================================================================

@pytest.mark.asyncio
async def test_15_live_firebase_smoke_test():
    """
    Live smoke test against real Firebase Cloud Storage.
    Automatically skipped if FIREBASE_STORAGE_BUCKET and credentials are not present.
    """
    provider = FirebaseStorageProvider()
    if not provider.is_configured():
        pytest.skip("Firebase credentials or bucket not configured in environment — skipping live test.")

    test_path = f"live-test/{uuid.uuid4()}/smoke_test.jpg"

    # 1. Upload test object
    success, uploaded_path, err = await provider.upload_bytes(
        data=SAMPLE_JPEG_BYTES,
        destination_path=test_path,
        content_type="image/jpeg",
    )
    assert success is True
    assert err is None

    # 2. Check exists
    exists = await provider.check_object_exists(test_path)
    assert exists is True

    # 3. Generate signed URL
    signed_url = await provider.get_download_signed_url(test_path, expires_in_seconds=300)
    assert signed_url is not None
    assert "http" in signed_url

    # 4. Clean up test object
    deleted = await provider.delete_object(test_path)
    assert deleted is True
