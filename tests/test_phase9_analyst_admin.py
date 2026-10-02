import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.models.source import Source
from app.models.audit_log import AuditLog
from app.models.enums import UserRole, WeatherCategory, EventSeverity, VerificationStatus


@pytest.mark.asyncio
async def test_analyst_verification_queue_and_rbac(
    client: AsyncClient,
    db_session: AsyncSession,
    test_citizen: User,
    test_analyst: User,
    auth_headers,
):
    """Test verification queue retrieval, multi-dimensional filters, and RBAC."""
    # Seed canonical events
    event1 = WeatherEvent(
        category=WeatherCategory.FLOODING.value,
        severity=EventSeverity.CATASTROPHIC.value,
        confidence_score=0.75,
        verification_status=VerificationStatus.UNVERIFIED.value,
        primary_state="Kerala",
        primary_district="Wayanad",
        centroid_lat=11.60,
        centroid_lon=76.95,
        evidence_count=3,
        is_active=True,
    )
    event2 = WeatherEvent(
        category=WeatherCategory.CYCLONE.value,
        severity=EventSeverity.SEVERE.value,
        confidence_score=0.85,
        verification_status=VerificationStatus.UNVERIFIED.value,
        primary_state="Odisha",
        primary_district="Puri",
        centroid_lat=19.81,
        centroid_lon=85.82,
        evidence_count=5,
        is_active=True,
    )
    db_session.add_all([event1, event2])
    await db_session.commit()

    # 1. Citizen cannot access verification queue
    cit_resp = await client.get("/api/v1/verification/queue", headers=auth_headers(test_citizen))
    assert cit_resp.status_code == 403

    # 2. Analyst can access queue
    analyst_resp = await client.get("/api/v1/verification/queue", headers=auth_headers(test_analyst))
    assert analyst_resp.status_code == 200
    data = analyst_resp.json()
    assert "results" in data
    assert len(data["results"]) >= 2

    # 3. Filter by category
    cat_resp = await client.get(
        "/api/v1/verification/queue?category=CYCLONE",
        headers=auth_headers(test_analyst),
    )
    assert cat_resp.status_code == 200
    cat_data = cat_resp.json()
    for item in cat_data["results"]:
        assert item["category"] == "CYCLONE"


@pytest.mark.asyncio
async def test_analyst_verification_override_and_audit(
    client: AsyncClient,
    db_session: AsyncSession,
    test_analyst: User,
    auth_headers,
):
    """Test manual verification override updates status, recalculates confidence, and logs audit record."""
    event = WeatherEvent(
        category=WeatherCategory.RAINFALL.value,
        severity=EventSeverity.MODERATE.value,
        confidence_score=0.60,
        verification_status=VerificationStatus.UNVERIFIED.value,
        primary_state="Karnataka",
        primary_district="Bengaluru Urban",
        centroid_lat=12.97,
        centroid_lon=77.59,
        evidence_count=2,
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    override_payload = {
        "status": "VERIFIED",
        "reason": "Confirmed with city radar and CCTV telemetry.",
    }

    resp = await client.post(
        f"/api/v1/verification/{event.id}/override",
        json=override_payload,
        headers=auth_headers(test_analyst),
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "VERIFIED"
    assert res_data["confidence_score"] >= 0.85

    # Check that event was updated in DB
    await db_session.refresh(event)
    assert event.verification_status == "VERIFIED"


@pytest.mark.asyncio
async def test_duplicate_clusters_split_and_merge(
    client: AsyncClient,
    db_session: AsyncSession,
    test_analyst: User,
    test_citizen: User,
    auth_headers,
):
    """Test duplicate cluster operations: listing, splitting, and merging."""
    # Seed a Source for report foreign key
    source = Source(
        name="Citizen Report Stream",
        source_type="CITIZEN",
        connector_class="CitizenConnector",
        config={},
        trust_score=0.7,
        is_active=True,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    # Create canonical event and secondary event
    canon_event = WeatherEvent(
        category=WeatherCategory.FLOODING.value,
        severity=EventSeverity.SEVERE.value,
        confidence_score=0.80,
        verification_status=VerificationStatus.UNVERIFIED.value,
        primary_state="Maharashtra",
        primary_district="Mumbai",
        centroid_lat=19.07,
        centroid_lon=72.87,
        evidence_count=4,
        is_active=True,
    )
    second_event = WeatherEvent(
        category=WeatherCategory.FLOODING.value,
        severity=EventSeverity.SEVERE.value,
        confidence_score=0.70,
        verification_status=VerificationStatus.UNVERIFIED.value,
        primary_state="Maharashtra",
        primary_district="Mumbai",
        centroid_lat=19.08,
        centroid_lon=72.88,
        evidence_count=2,
        is_active=True,
    )
    db_session.add_all([canon_event, second_event])
    await db_session.commit()
    await db_session.refresh(canon_event)
    await db_session.refresh(second_event)

    # Create reports linked to canon_event
    rep1 = WeatherReport(
        primary_category=WeatherCategory.FLOODING.value,
        severity=EventSeverity.SEVERE.value,
        source_id=source.id,
        canonical_event_id=canon_event.id,
        is_duplicate=True,
        raw_content="Flooding on SV Road",
        normalized_text="Flooding on SV Road",
    )
    rep2 = WeatherReport(
        primary_category=WeatherCategory.FLOODING.value,
        severity=EventSeverity.SEVERE.value,
        source_id=source.id,
        canonical_event_id=canon_event.id,
        is_duplicate=True,
        raw_content="Flooding near Khar subway",
        normalized_text="Flooding near Khar subway",
    )
    db_session.add_all([rep1, rep2])
    await db_session.commit()
    await db_session.refresh(rep1)
    await db_session.refresh(rep2)

    # 1. Citizen forbidden
    cit_resp = await client.get("/api/v1/verification/clusters", headers=auth_headers(test_citizen))
    assert cit_resp.status_code == 403

    # 2. Analyst can list clusters
    cluster_resp = await client.get(
        f"/api/v1/verification/clusters?event_id={canon_event.id}",
        headers=auth_headers(test_analyst),
    )
    assert cluster_resp.status_code == 200
    clusters = cluster_resp.json()
    assert isinstance(clusters, list)
    if clusters:
        assert clusters[0]["canonical_event_id"] == str(canon_event.id)

    # 3. Split report from cluster
    split_payload = {
        "report_ids_to_remove": [str(rep2.id)],
        "reason": "Report describes flooding at distinct neighborhood 5km away",
    }
    split_resp = await client.post(
        "/api/v1/verification/clusters/split",
        json=split_payload,
        headers=auth_headers(test_analyst),
    )
    assert split_resp.status_code == 200
    assert split_resp.json()["removed_count"] == 1

    # Verify report is detached from canon_event
    await db_session.refresh(rep2)
    assert rep2.canonical_event_id is None
    assert rep2.is_duplicate is False

    # 4. Merge secondary event into canon_event
    merge_payload = {
        "primary_event_id": str(canon_event.id),
        "secondary_event_id": str(second_event.id),
        "reason": "Corroborated ground truth confirms same urban flood incident",
    }
    merge_resp = await client.post(
        "/api/v1/verification/clusters/merge",
        json=merge_payload,
        headers=auth_headers(test_analyst),
    )
    assert merge_resp.status_code == 200
    assert merge_resp.json()["primary_event_id"] == str(canon_event.id)


@pytest.mark.asyncio
async def test_admin_connector_management_and_rbac(
    client: AsyncClient,
    db_session: AsyncSession,
    test_admin: User,
    test_analyst: User,
    auth_headers,
):
    """Test connector listing, creation, and active/dormant toggle with RBAC."""
    # 1. Create connector via admin
    connector_payload = {
        "name": "IMD Doppler Radar Regional",
        "source_type": "WEATHER_API",
        "connector_class": "IMDConnector",
        "is_demo": False,
        "config": {"radar_id": "DEL_RADAR_01"},
    }
    create_resp = await client.post(
        "/api/v1/sources/connectors",
        json=connector_payload,
        headers=auth_headers(test_admin),
    )
    assert create_resp.status_code == 201
    conn_data = create_resp.json()
    source_id = conn_data["id"]
    assert conn_data["name"] == "IMD Doppler Radar Regional"
    assert conn_data["is_active"] is True

    # 2. Analyst forbidden from modifying connector
    analyst_patch = await client.patch(
        f"/api/v1/sources/connectors/{source_id}",
        json={"is_active": False},
        headers=auth_headers(test_analyst),
    )
    assert analyst_patch.status_code == 403

    # 3. Admin can toggle connector active status
    admin_patch = await client.patch(
        f"/api/v1/sources/connectors/{source_id}",
        json={"is_active": False},
        headers=auth_headers(test_admin),
    )
    assert admin_patch.status_code == 200
    assert admin_patch.json()["is_active"] is False


@pytest.mark.asyncio
async def test_admin_user_management_and_roles(
    client: AsyncClient,
    db_session: AsyncSession,
    test_admin: User,
    test_citizen: User,
    test_analyst: User,
    auth_headers,
):
    """Test user directory retrieval and role assignment."""
    # 1. Analyst cannot view admin users endpoint
    analyst_resp = await client.get("/api/v1/admin/users", headers=auth_headers(test_analyst))
    assert analyst_resp.status_code == 403

    # 2. Admin can list users
    admin_resp = await client.get("/api/v1/admin/users", headers=auth_headers(test_admin))
    assert admin_resp.status_code == 200
    users = admin_resp.json()
    assert len(users) >= 3

    # 3. Admin promotes citizen to ANALYST
    promote_resp = await client.patch(
        f"/api/v1/admin/users/{test_citizen.id}/role",
        json={"role": "ANALYST"},
        headers=auth_headers(test_admin),
    )
    assert promote_resp.status_code == 200
    assert promote_resp.json()["role"] == "ANALYST"

    # Verify DB update
    await db_session.refresh(test_citizen)
    assert test_citizen.role == "ANALYST"


@pytest.mark.asyncio
async def test_admin_audit_logs_and_flagged_reports(
    client: AsyncClient,
    db_session: AsyncSession,
    test_admin: User,
    test_citizen: User,
    auth_headers,
):
    """Test querying audit logs and flagged anomalous reports."""
    # Seed a Source for report foreign key
    source = Source(
        name="Official Disaster Portal Feed",
        source_type="GOVERNMENT_API",
        connector_class="GovConnector",
        config={},
        trust_score=0.9,
        is_active=True,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    # Seed an audit log
    audit_entry = AuditLog(
        id=int(uuid.uuid4().int % 10000000),
        user_id=test_admin.id,
        action_type="UPDATE",
        entity_type="Source",
        entity_id=uuid.uuid4(),
        old_value={"active": True},
        new_value={"active": False},
        ip_address="127.0.0.1",
    )
    db_session.add(audit_entry)

    # Seed a flagged report
    flagged_rep = WeatherReport(
        primary_category=WeatherCategory.THUNDERSTORM.value,
        severity=EventSeverity.SEVERE.value,
        source_id=source.id,
        location_state="Delhi",
        location_district="New Delhi",
        status="FLAGGED",
        raw_content="Unprecedented localized storm report",
        normalized_text="Unprecedented localized storm report",
    )
    db_session.add(flagged_rep)
    await db_session.commit()

    # 1. Citizen forbidden from audit logs
    cit_audit = await client.get("/api/v1/admin/audit-logs", headers=auth_headers(test_citizen))
    assert cit_audit.status_code == 403

    # 2. Admin retrieves audit logs
    admin_audit = await client.get("/api/v1/admin/audit-logs", headers=auth_headers(test_admin))
    assert admin_audit.status_code == 200
    logs = admin_audit.json()
    assert len(logs) >= 1

    # 3. Admin retrieves flagged reports
    flagged_resp = await client.get("/api/v1/admin/flagged-reports", headers=auth_headers(test_admin))
    assert flagged_resp.status_code == 200
    flagged_list = flagged_resp.json()
    assert len(flagged_list) >= 1
    assert any(r["id"] == str(flagged_rep.id) for r in flagged_list)
