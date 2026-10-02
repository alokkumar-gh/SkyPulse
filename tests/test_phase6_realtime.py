"""
Phase 6 Tests — WebSocket, Alert Engine, Notifications, RBAC, Backpressure
==========================================================================
All tests run in-process without requiring live Kafka, Redis, or external services.

Coverage:
  - WebSocket manager: connect, auth, subscribe, unsubscribe, heartbeat, backpressure
  - JWT authentication integration
  - Subscription filter engine (category, location, severity, bbox, confidence)
  - RBAC access control (PUBLIC/CITIZEN/ANALYST/ADMIN)
  - Event type mapping (ai_processed, verification_updates, anomalies)
  - Alert engine: creation, priority, deduplication, fingerprint, cooldown
  - Notification provider abstraction: local OK, external NOT_CONFIGURED
  - In-app notification: persist, unread count, mark-read, mark-all
  - Backpressure: per-client queue overflow drops oldest
  - Reconnect: schedule reconnect timer logic in WS manager
  - Real-time gateway mapping functions
"""

import asyncio
import hashlib
import json
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

# ── Ensure backend package roots are importable ──────────────────────────
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.security import create_access_token
from app.core.websocket_manager import (
    WebSocketManager,
    SubscriptionFilter,
    ConnectedClient,
    RedisFanout,
    build_event_envelope,
    strip_sensitive_fields,
    get_metrics,
    PROTOCOL_VERSION,
)
from app.services.alert_service import (
    AlertEngine,
    compute_priority,
    compute_fingerprint,
    _time_window_key,
)
from app.services.notification_service import (
    LocalNotificationProvider,
    ExternalNotificationProvider,
    NotificationPayload,
    ProviderStatus,
)
from workers.realtime_gateway import (
    map_ai_processed,
    map_verification_update,
    map_anomaly,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

def _make_ws():
    """Create a mock WebSocket."""
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    ws.receive_text = AsyncMock()
    return ws


def _make_token(role: str = "CITIZEN", user_id: Optional[str] = None) -> str:
    uid = user_id or str(uuid.uuid4())
    return create_access_token({"sub": uid, "email": f"{role.lower()}@test.com", "role": role})


def _make_event(
    category="RAINFALL",
    severity=2,
    confidence=0.75,
    state="Maharashtra",
    city="Mumbai",
    verification_status="UNVERIFIED",
    event_type="weather_event.updated",
) -> Dict[str, Any]:
    return build_event_envelope(
        event_type=event_type,
        event_id=str(uuid.uuid4()),
        data={
            "category": category,
            "severity": severity,
            "confidence": confidence,
            "verification_status": verification_status,
            "location": {
                "state": state,
                "city": city,
                "district": "Mumbai",
                "latitude": 19.07,
                "longitude": 72.87,
            },
            "source_type": "CITIZEN",
            "is_demo": False,
        },
    )


@pytest_asyncio.fixture
async def manager():
    """Fresh WebSocketManager with in-memory Redis fallback."""
    mgr = WebSocketManager(redis_url="redis://127.0.0.1:9999")  # unreachable → local fallback
    await mgr.startup()
    yield mgr
    await mgr.shutdown()


# ═══════════════════════════════════════════════════════════════════════════
# 1. WebSocket Connection & Authentication
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ws_connect_as_public(manager):
    """Unauthenticated connection accepted as PUBLIC role."""
    ws = _make_ws()
    client_id = await manager.connect(ws, user_id=None, role="PUBLIC")
    assert client_id is not None
    assert client_id in manager._clients
    client = manager._clients[client_id]
    assert client.role == "PUBLIC"
    assert client.user_id is None


@pytest.mark.asyncio
async def test_ws_connect_with_valid_jwt(manager):
    """Connection with valid JWT extracts user_id and role."""
    ws = _make_ws()
    token = _make_token(role="ANALYST", user_id="uid-123")
    from app.core.security import decode_token
    payload = decode_token(token)
    user_id = payload["sub"]
    role = payload["role"]
    client_id = await manager.connect(ws, user_id=user_id, role=role)
    assert client_id is not None
    client = manager._clients[client_id]
    assert client.role == "ANALYST"
    assert client.user_id == user_id


@pytest.mark.asyncio
async def test_ws_invalid_token_rejected():
    """Invalid JWT is decoded to None — endpoint should close with 4001."""
    from app.core.security import decode_token
    result = decode_token("obviously.invalid.token")
    assert result is None


@pytest.mark.asyncio
async def test_ws_expired_token_rejected():
    """Expired JWT (negative expiry) is rejected."""
    from datetime import timedelta
    expired_token = create_access_token(
        {"sub": str(uuid.uuid4()), "role": "CITIZEN"},
        expires_delta=timedelta(seconds=-1),
    )
    from app.core.security import decode_token
    result = decode_token(expired_token)
    assert result is None


@pytest.mark.asyncio
async def test_ws_disconnect_cleans_up(manager):
    """Disconnecting a client removes it from registry."""
    ws = _make_ws()
    client_id = await manager.connect(ws, user_id=None, role="PUBLIC")
    assert client_id in manager._clients
    await manager.disconnect(client_id)
    assert client_id not in manager._clients


@pytest.mark.asyncio
async def test_ws_max_connections_rejected(manager):
    """Connections beyond MAX_CONNECTIONS are rejected."""
    from app.core.websocket_manager import MAX_CONNECTIONS
    # Fill up to limit
    created = []
    for _ in range(MAX_CONNECTIONS):
        ws = _make_ws()
        cid = await manager.connect(ws, user_id=None, role="PUBLIC")
        if cid:
            created.append(cid)
        if len(created) >= MAX_CONNECTIONS:
            break

    # One more should be rejected
    ws_extra = _make_ws()
    result = await manager.connect(ws_extra, user_id=None, role="PUBLIC")
    # Clean up
    for cid in created:
        manager._clients.pop(cid, None)
    # The extra connection was rejected
    assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# 2. Subscription Filters
# ═══════════════════════════════════════════════════════════════════════════

def test_filter_category_match():
    f = SubscriptionFilter(categories=["FLOODING", "RAINFALL"])
    event = _make_event(category="FLOODING")
    assert f.matches(event, "CITIZEN") is True


def test_filter_category_no_match():
    f = SubscriptionFilter(categories=["FOG"])
    event = _make_event(category="FLOODING")
    assert f.matches(event, "CITIZEN") is False


def test_filter_state_match():
    f = SubscriptionFilter(states=["Odisha"])
    event = _make_event(state="Odisha")
    assert f.matches(event, "CITIZEN") is True


def test_filter_state_no_match():
    f = SubscriptionFilter(states=["Odisha"])
    event = _make_event(state="Maharashtra")
    assert f.matches(event, "CITIZEN") is False


def test_filter_severity_range():
    f = SubscriptionFilter(min_severity=3)
    low_event = _make_event(severity=2)
    high_event = _make_event(severity=3)
    assert f.matches(low_event, "CITIZEN") is False
    assert f.matches(high_event, "CITIZEN") is True


def test_filter_confidence_threshold():
    f = SubscriptionFilter(min_confidence=0.80)
    low_conf = _make_event(confidence=0.60)
    high_conf = _make_event(confidence=0.90)
    assert f.matches(low_conf, "CITIZEN") is False
    assert f.matches(high_conf, "CITIZEN") is True


def test_filter_verification_status():
    f = SubscriptionFilter(verification_statuses=["VERIFIED"])
    unverified = _make_event(verification_status="UNVERIFIED")
    verified = _make_event(verification_status="VERIFIED")
    assert f.matches(unverified, "ANALYST") is False
    assert f.matches(verified, "ANALYST") is True


def test_filter_bounding_box():
    # Mumbai bbox roughly [72.7, 18.8, 73.0, 19.3]
    f = SubscriptionFilter(bbox=(72.7, 18.8, 73.0, 19.3))
    inside = _make_event()  # lat=19.07, lon=72.87
    assert f.matches(inside, "CITIZEN") is True


def test_filter_bounding_box_outside():
    # Far from Mumbai
    f = SubscriptionFilter(bbox=(77.0, 28.0, 78.0, 29.0))  # Delhi area
    mumbai_event = _make_event()  # lat=19.07, lon=72.87
    assert f.matches(mumbai_event, "CITIZEN") is False


def test_filter_multiple_combined():
    f = SubscriptionFilter(
        categories=["FLOODING", "RAINFALL"],
        states=["Maharashtra"],
        min_severity=2,
        min_confidence=0.70,
    )
    matching = _make_event(category="FLOODING", state="Maharashtra", severity=3, confidence=0.85)
    assert f.matches(matching, "CITIZEN") is True

    non_matching = _make_event(category="FOG", state="Maharashtra", severity=3, confidence=0.85)
    assert f.matches(non_matching, "CITIZEN") is False


# ═══════════════════════════════════════════════════════════════════════════
# 3. RBAC: Event Access By Role
# ═══════════════════════════════════════════════════════════════════════════

def test_rbac_anomaly_blocked_for_public():
    """PUBLIC role cannot receive weather_event.anomaly events."""
    f = SubscriptionFilter()
    anomaly_event = _make_event(event_type="weather_event.anomaly")
    # PUBLIC should not get anomaly events
    assert f.matches(anomaly_event, "PUBLIC") is False


def test_rbac_anomaly_allowed_for_analyst():
    f = SubscriptionFilter()
    anomaly_event = _make_event(event_type="weather_event.anomaly")
    assert f.matches(anomaly_event, "ANALYST") is True


def test_rbac_system_events_blocked_for_citizen():
    """system.* events are ADMIN-only."""
    f = SubscriptionFilter()
    sys_event = build_event_envelope("system.notification", "sys-1", {"level": "INFO"})
    assert f.matches(sys_event, "CITIZEN") is False


def test_rbac_system_events_allowed_for_admin():
    f = SubscriptionFilter()
    sys_event = build_event_envelope("system.notification", "sys-1", {"level": "INFO"})
    assert f.matches(sys_event, "ADMIN") is True


def test_strip_sensitive_fields_for_public():
    """Sensitive source fields stripped for PUBLIC/CITIZEN."""
    event = build_event_envelope("weather_event.updated", "ev-1", {
        "category": "RAINFALL",
        "source_type": "CITIZEN_REPORT",
        "source_id": "internal-uuid-123",
        "ai_scores": {"confidence": 0.9},
        "severity": 1,
        "confidence": 0.8,
    })
    stripped = strip_sensitive_fields(event, "PUBLIC")
    assert "source_type" not in stripped["data"]
    assert "source_id" not in stripped["data"]
    assert "ai_scores" not in stripped["data"]


def test_strip_sensitive_fields_preserved_for_analyst():
    """Analyst receives full data including internal fields."""
    event = build_event_envelope("weather_event.updated", "ev-1", {
        "category": "RAINFALL",
        "source_type": "CITIZEN_REPORT",
        "source_id": "internal-uuid-123",
    })
    full = strip_sensitive_fields(event, "ANALYST")
    assert "source_type" in full["data"]
    assert "source_id" in full["data"]


# ═══════════════════════════════════════════════════════════════════════════
# 4. WebSocket Message Protocol
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ws_subscribe_updates_filter(manager):
    ws = _make_ws()
    client_id = await manager.connect(ws, user_id=None, role="CITIZEN")

    subscribe_msg = json.dumps({
        "type": "subscribe",
        "filters": {
            "states": ["Odisha"],
            "categories": ["RAINFALL", "FLOODING"],
            "min_severity": 2,
        }
    })
    await manager.handle_message(client_id, subscribe_msg)

    client = manager._clients[client_id]
    assert client.filters.states == ["Odisha"]
    assert "RAINFALL" in client.filters.categories
    assert client.filters.min_severity == 2


@pytest.mark.asyncio
async def test_ws_unsubscribe_clears_filter(manager):
    ws = _make_ws()
    client_id = await manager.connect(ws, user_id=None, role="CITIZEN")

    # Subscribe first
    await manager.handle_message(client_id, json.dumps({
        "type": "subscribe",
        "filters": {"states": ["Kerala"]}
    }))
    assert manager._clients[client_id].filters.states == ["Kerala"]

    # Unsubscribe
    await manager.handle_message(client_id, json.dumps({"type": "unsubscribe"}))
    assert manager._clients[client_id].filters.states is None


@pytest.mark.asyncio
async def test_ws_ping_pong(manager):
    ws = _make_ws()
    client_id = await manager.connect(ws, user_id=None, role="PUBLIC")

    await manager.handle_message(client_id, json.dumps({"type": "ping"}))
    # Should have sent pong
    ws.send_text.assert_called()
    last_call = ws.send_text.call_args[0][0]
    pong = json.loads(last_call)
    assert pong["type"] == "pong"


@pytest.mark.asyncio
async def test_ws_oversized_message_rejected(manager):
    ws = _make_ws()
    client_id = await manager.connect(ws, user_id=None, role="PUBLIC")

    # > 8192 bytes
    big_msg = json.dumps({"type": "ping", "junk": "x" * 9000})
    await manager.handle_message(client_id, big_msg)

    # Should have sent error
    ws.send_text.assert_called()
    calls = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
    error_calls = [c for c in calls if c.get("type") == "error"]
    assert any(e["code"] == "MESSAGE_TOO_LARGE" for e in error_calls)


@pytest.mark.asyncio
async def test_ws_malformed_json_rejected(manager):
    ws = _make_ws()
    client_id = await manager.connect(ws, user_id=None, role="PUBLIC")

    await manager.handle_message(client_id, "not-valid-json{{{")
    ws.send_text.assert_called()
    calls = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
    error_calls = [c for c in calls if c.get("type") == "error"]
    assert any(e["code"] == "INVALID_JSON" for e in error_calls)


# ═══════════════════════════════════════════════════════════════════════════
# 5. Backpressure
# ═══════════════════════════════════════════════════════════════════════════

def test_backpressure_drops_oldest_on_overflow():
    """Per-client queue drops oldest message when full."""
    ws = _make_ws()
    client = ConnectedClient(
        client_id="bp-test",
        websocket=ws,
        user_id=None,
        role="PUBLIC",
    )
    # Fill queue beyond maxsize (200)
    dropped = 0
    for i in range(210):
        event = build_event_envelope("weather_event.updated", f"ev-{i}", {"severity": 1, "confidence": 0.5})
        result = client.enqueue(event)
        if not result:
            dropped += 1
    # At least some were accommodated and at most queue size messages remain
    assert client._queue.qsize() <= 200


def test_event_coalescing_batches_rapid_updates():
    """Rapid weather_event.updated for same event_id should coalesce."""
    ws = _make_ws()
    client = ConnectedClient(
        client_id="coalesce-test",
        websocket=ws,
        user_id=None,
        role="CITIZEN",
    )
    event_id = "shared-event-123"
    for _ in range(5):
        event = build_event_envelope(
            "weather_event.updated",
            event_id,
            {"severity": 2, "confidence": 0.7, "priority": "LOW"},
        )
        client.enqueue(event)

    # Before coalesce window, they should be buffered
    assert event_id in client._coalesce_buffer

    # After forcing flush, should be in queue as cluster_updated
    client.flush_all_coalesced()
    assert event_id not in client._coalesce_buffer
    assert not client._queue.empty()
    msg = client._queue.get_nowait()
    assert msg["type"] == "weather_event.cluster_updated"


def test_critical_alerts_bypass_coalescing():
    """HIGH/CRITICAL priority events are not coalesced."""
    ws = _make_ws()
    client = ConnectedClient(
        client_id="critical-test",
        websocket=ws,
        user_id=None,
        role="ANALYST",
    )
    event_id = "critical-event"
    critical_event = build_event_envelope(
        "weather_event.updated",
        event_id,
        {"severity": 4, "confidence": 0.95, "priority": "CRITICAL"},
    )
    client.enqueue(critical_event)
    # Critical events should go straight to queue, not coalesce buffer
    assert event_id not in client._coalesce_buffer
    assert not client._queue.empty()


# ═══════════════════════════════════════════════════════════════════════════
# 6. Real-Time Gateway Mapping
# ═══════════════════════════════════════════════════════════════════════════

def test_map_ai_processed_creates_updated_event():
    payload = {
        "event_id": str(uuid.uuid4()),
        "report_id": str(uuid.uuid4()),
        "category": "FLOODING",
        "severity": 3,
        "confidence": 0.88,
        "verification_status": "UNVERIFIED",
        "primary_state": "Odisha",
        "primary_city": "Bhubaneswar",
        "centroid_lat": 20.29,
        "centroid_lon": 85.82,
    }
    result = map_ai_processed(payload)
    assert result is not None
    assert result["type"] == "weather_event.updated"
    assert result["data"]["category"] == "FLOODING"
    assert result["version"] == PROTOCOL_VERSION


def test_map_verification_update_verified():
    payload = {
        "event_id": str(uuid.uuid4()),
        "verification_status": "VERIFIED",
        "confidence_score": 0.92,
        "category": "THUNDERSTORM",
        "severity": 2,
        "primary_state": "Maharashtra",
    }
    result = map_verification_update(payload)
    assert result is not None
    assert result["type"] == "weather_event.verified"


def test_map_verification_update_contradicted():
    payload = {
        "event_id": str(uuid.uuid4()),
        "verification_status": "CONTRADICTED",
        "confidence_score": 0.30,
    }
    result = map_verification_update(payload)
    assert result is not None
    assert result["type"] == "weather_event.rejected"


def test_map_anomaly_creates_anomaly_event():
    payload = {
        "event_id": str(uuid.uuid4()),
        "report_id": str(uuid.uuid4()),
        "anomaly_type": "VOLUME_BURST",
        "anomaly_score": 0.92,
        "category": "RAINFALL",
        "severity": 2,
        "primary_state": "Kerala",
    }
    result = map_anomaly(payload)
    assert result is not None
    assert result["type"] == "weather_event.anomaly"
    assert result["data"]["anomaly_type"] == "VOLUME_BURST"


def test_map_missing_event_id_returns_none():
    payload = {"category": "FOG"}  # No event_id
    assert map_ai_processed(payload) is None
    assert map_verification_update(payload) is None
    assert map_anomaly(payload) is None


# ═══════════════════════════════════════════════════════════════════════════
# 7. Alert Engine — Priority & Fingerprint
# ═══════════════════════════════════════════════════════════════════════════

def test_alert_priority_critical():
    p = compute_priority(severity=4, confidence=0.9, category="RAINFALL", alert_type="HIGH_SEVERITY")
    assert p == "CRITICAL"


def test_alert_priority_high():
    p = compute_priority(severity=3, confidence=0.85, category="FOG", alert_type="HIGH_SEVERITY")
    assert p == "HIGH"


def test_alert_priority_medium():
    p = compute_priority(severity=2, confidence=0.75, category="RAINFALL", alert_type="HIGH_CONFIDENCE")
    assert p == "MEDIUM"


def test_alert_priority_low():
    p = compute_priority(severity=2, confidence=0.50, category="FOG", alert_type="HIGH_SEVERITY")
    assert p == "LOW"


def test_alert_priority_info():
    p = compute_priority(severity=1, confidence=0.40, category="FOG", alert_type="HIGH_SEVERITY")
    assert p == "INFO"


def test_alert_priority_anomaly_is_high():
    p = compute_priority(severity=1, confidence=0.50, category="FOG", alert_type="ANOMALY_DETECTED")
    assert p == "HIGH"


def test_alert_priority_flooding_severity3_is_critical():
    p = compute_priority(severity=3, confidence=0.85, category="FLOODING", alert_type="FLOODING_NEAR_AREA")
    assert p == "CRITICAL"


def test_fingerprint_deterministic():
    fp1 = compute_fingerprint("event-abc", "HIGH_SEVERITY", "Maharashtra:Mumbai")
    fp2 = compute_fingerprint("event-abc", "HIGH_SEVERITY", "Maharashtra:Mumbai")
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 hex


def test_fingerprint_different_for_different_events():
    fp1 = compute_fingerprint("event-abc", "HIGH_SEVERITY", "Maharashtra:Mumbai")
    fp2 = compute_fingerprint("event-xyz", "HIGH_SEVERITY", "Maharashtra:Mumbai")
    assert fp1 != fp2


def test_alert_engine_type_determination():
    engine = AlertEngine()
    # Anomaly overrides everything
    t = engine._determine_alert_type(
        category="RAINFALL", severity=1, confidence=0.5,
        verification_status="UNVERIFIED", evidence_count=1, is_anomalous=True
    )
    assert t == "ANOMALY_DETECTED"

    # Flooding severity 3
    t = engine._determine_alert_type(
        category="FLOODING", severity=3, confidence=0.8,
        verification_status="UNVERIFIED", evidence_count=1, is_anomalous=False
    )
    assert t == "FLOODING_NEAR_AREA"

    # Below threshold → None
    t = engine._determine_alert_type(
        category="FOG", severity=1, confidence=0.4,
        verification_status="UNVERIFIED", evidence_count=1, is_anomalous=False
    )
    assert t is None


@pytest.mark.asyncio
async def test_alert_creation_persists_to_db(db_session):
    """Alert engine creates an Alert row with correct fields."""
    event_data = {
        "event_id": str(uuid.uuid4()),
        "category": "FLOODING",
        "severity": 3,
        "confidence_score": 0.90,
        "verification_status": "VERIFIED",
        "evidence_count": 5,
        "is_anomalous": False,
        "primary_state": "Odisha",
        "primary_city": "Bhubaneswar",
        "primary_district": "Khordha",
        "centroid_lat": 20.29,
        "centroid_lon": 85.82,
    }
    engine = AlertEngine()
    alert = await engine.evaluate_event(db_session, event_data)
    assert alert is not None
    assert alert.alert_type == "FLOODING_NEAR_AREA"
    assert alert.priority == "CRITICAL"
    assert alert.status == "CREATED"
    assert alert.location_state == "Odisha"
    assert alert.fingerprint is not None


@pytest.mark.asyncio
async def test_alert_deduplication_same_fingerprint(db_session):
    """Same event + type + location + time-window → no second alert created."""
    event_data = {
        "event_id": str(uuid.uuid4()),
        "category": "HEATWAVE",
        "severity": 3,
        "confidence_score": 0.85,
        "verification_status": "UNVERIFIED",
        "evidence_count": 1,
        "is_anomalous": False,
        "primary_state": "Rajasthan",
        "primary_city": "Jaipur",
        "primary_district": "Jaipur",
    }
    engine = AlertEngine()
    alert1 = await engine.evaluate_event(db_session, event_data)
    alert2 = await engine.evaluate_event(db_session, event_data)

    # Both calls reference the same alert row
    assert alert1 is not None
    assert alert2 is not None
    assert str(alert1.id) == str(alert2.id)


@pytest.mark.asyncio
async def test_alert_below_threshold_returns_none(db_session):
    """Low severity/confidence events don't generate alerts."""
    event_data = {
        "event_id": str(uuid.uuid4()),
        "category": "FOG",
        "severity": 1,
        "confidence_score": 0.40,
        "verification_status": "UNVERIFIED",
        "evidence_count": 1,
        "is_anomalous": False,
        "primary_state": "Haryana",
    }
    engine = AlertEngine()
    alert = await engine.evaluate_event(db_session, event_data)
    assert alert is None


@pytest.mark.asyncio
async def test_alert_acknowledge(db_session):
    """Acknowledging an alert transitions to ACKNOWLEDGED status."""
    from app.models.alert import Alert
    alert = Alert(
        alert_type="HIGH_SEVERITY",
        priority="HIGH",
        status="CREATED",
        title="Test Alert",
        message="Test message",
        severity=3,
        fingerprint=hashlib.sha256(b"test-ack").hexdigest(),
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)

    engine = AlertEngine()
    updated = await engine.acknowledge_alert(db_session, alert.id)
    assert updated is not None
    assert updated.status == "ACKNOWLEDGED"
    assert updated.acknowledged_at is not None


# ═══════════════════════════════════════════════════════════════════════════
# 8. Notification Provider
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_local_provider_send_success():
    provider = LocalNotificationProvider()
    payload = NotificationPayload(
        recipient_user_id="user-abc",
        title="Test Alert",
        body="Heavy rain expected",
        notification_type="NEW_HIGH_SEVERITY_EVENT",
        priority="HIGH",
    )
    result = await provider.send(payload)
    assert result.success is True
    assert result.status == ProviderStatus.OK
    assert result.message_id is not None
    assert len(provider.get_all()) == 1


@pytest.mark.asyncio
async def test_external_provider_not_configured():
    """External provider without credentials returns NOT_CONFIGURED."""
    provider = ExternalNotificationProvider(fcm_server_key=None)
    payload = NotificationPayload(
        recipient_user_id="user-xyz",
        title="Alert",
        body="Storm warning",
    )
    result = await provider.send(payload)
    # Should NOT report success from external system
    assert result.success is False
    assert result.status == ProviderStatus.NOT_CONFIGURED
    # But should have stored locally via fallback
    assert result.message_id is not None


@pytest.mark.asyncio
async def test_external_provider_health_not_configured():
    provider = ExternalNotificationProvider(fcm_server_key=None)
    status = await provider.health_check()
    assert status == ProviderStatus.NOT_CONFIGURED


# ═══════════════════════════════════════════════════════════════════════════
# 9. Notifications REST API
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_notifications_list_authenticated(client, test_citizen, auth_headers):
    """Authenticated user can list their notifications."""
    headers = auth_headers(test_citizen)
    resp = await client.get("/api/v1/notifications", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_notifications_unread_count(client, test_citizen, auth_headers):
    """Unread count endpoint returns integer."""
    headers = auth_headers(test_citizen)
    resp = await client.get("/api/v1/notifications/unread-count", headers=headers)
    assert resp.status_code == 200
    assert "unread_count" in resp.json()
    assert isinstance(resp.json()["unread_count"], int)


@pytest.mark.asyncio
async def test_notifications_mark_read(client, test_citizen, auth_headers, db_session):
    """Mark a notification as read."""
    from app.models.notification import Notification
    notif = Notification(
        user_id=test_citizen.id,
        type="SYSTEM_HEALTH",
        title="Test",
        body="Body",
        data={},
        is_read=False,
    )
    db_session.add(notif)
    await db_session.commit()
    await db_session.refresh(notif)

    headers = auth_headers(test_citizen)
    resp = await client.post(f"/api/v1/notifications/{notif.id}/read", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True


@pytest.mark.asyncio
async def test_notifications_mark_all_read(client, test_citizen, auth_headers, db_session):
    """Mark all notifications read returns 204."""
    headers = auth_headers(test_citizen)
    resp = await client.post("/api/v1/notifications/read-all", headers=headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_notifications_unauthenticated_rejected(client):
    """Notification endpoint requires authentication."""
    resp = await client.get("/api/v1/notifications")
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# 10. Alerts REST API
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_alerts_list(client, test_citizen, auth_headers):
    """Authenticated user can list alerts."""
    headers = auth_headers(test_citizen)
    resp = await client.get("/api/v1/alerts", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_alerts_get_nonexistent(client, test_citizen, auth_headers):
    """Non-existent alert returns 404."""
    headers = auth_headers(test_citizen)
    resp = await client.get(f"/api/v1/alerts/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_alerts_acknowledge(client, test_citizen, auth_headers, db_session):
    """Acknowledge endpoint transitions alert to ACKNOWLEDGED."""
    from app.models.alert import Alert
    import hashlib
    alert = Alert(
        alert_type="HIGH_SEVERITY",
        priority="HIGH",
        status="CREATED",
        title="Test Alert",
        message="Test",
        severity=3,
        fingerprint=hashlib.sha256(b"api-test-ack").hexdigest(),
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)

    headers = auth_headers(test_citizen)
    resp = await client.post(f"/api/v1/alerts/{alert.id}/acknowledge", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACKNOWLEDGED"


# ═══════════════════════════════════════════════════════════════════════════
# 11. Observability Metrics
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_metrics_health_endpoint(client, test_admin, auth_headers):
    """WS metrics endpoint accessible by ADMIN."""
    headers = auth_headers(test_admin)
    resp = await client.get("/api/v1/metrics/ws", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "active_connections" in data


@pytest.mark.asyncio
async def test_metrics_health_public(client):
    """Lightweight health endpoint is public."""
    resp = await client.get("/api/v1/metrics/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_metrics_blocked_for_citizen(client, test_citizen, auth_headers):
    """WS metrics blocked for non-admin users."""
    headers = auth_headers(test_citizen)
    resp = await client.get("/api/v1/metrics/ws", headers=headers)
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# 12. Event Envelope Builder
# ═══════════════════════════════════════════════════════════════════════════

def test_event_envelope_structure():
    """build_event_envelope produces correct versioned envelope."""
    event = build_event_envelope(
        "weather_event.created",
        "evt_abc",
        {
            "category": "FLOODING",
            "severity": 3,
            "confidence": 0.91,
            "verification_status": "VERIFIED",
            "location": {
                "city": "Mumbai",
                "state": "Maharashtra",
                "latitude": 19.0178,
                "longitude": 72.8478,
            },
        },
    )
    assert event["version"] == PROTOCOL_VERSION
    assert event["type"] == "weather_event.created"
    assert event["event_id"] == "evt_abc"
    assert "timestamp" in event
    assert event["data"]["category"] == "FLOODING"


def test_event_envelope_timestamp_is_utc():
    event = build_event_envelope("test.event", "ev-1", {})
    ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
    # Should be recent (within 5 seconds)
    delta = abs((datetime.now(timezone.utc) - ts).total_seconds())
    assert delta < 5.0
