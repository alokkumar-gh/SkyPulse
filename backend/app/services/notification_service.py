"""
Notification Provider Abstraction — SkyPulse Phase 6
=====================================================
Abstraction layer for push notification delivery.

Providers:
  LocalNotificationProvider  — Stores notifications in-process (dev/demo/testing).
  ExternalNotificationProvider — Adapter for FCM/Web Push/APNs.
                                  Returns NOT_CONFIGURED when credentials absent.

Do NOT fabricate successful external delivery.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger("skypulse.notification_provider")


class ProviderStatus(str, Enum):
    OK = "OK"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


@dataclass
class NotificationPayload:
    recipient_user_id: str
    title: str
    body: str
    data: Dict[str, Any] = field(default_factory=dict)
    notification_type: str = "SYSTEM_HEALTH"
    priority: str = "MEDIUM"  # INFO | LOW | MEDIUM | HIGH | CRITICAL


@dataclass
class NotificationResult:
    success: bool
    provider: str
    status: ProviderStatus
    message_id: Optional[str] = None
    error: Optional[str] = None


class NotificationProvider(ABC):
    """Abstract base class for all notification providers."""

    @abstractmethod
    async def send(self, payload: NotificationPayload) -> NotificationResult:
        """Send a notification. Must never raise — return error in result."""
        ...

    @abstractmethod
    async def health_check(self) -> ProviderStatus:
        """Return current provider health status."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...


# ---------------------------------------------------------------------------
# Local / Development Provider
# ---------------------------------------------------------------------------
class LocalNotificationProvider(NotificationProvider):
    """
    Stores sent notifications in memory.
    Used during development, testing, and demo mode.
    """

    def __init__(self, max_stored: int = 10_000):
        self._store: List[Dict[str, Any]] = []
        self._max_stored = max_stored

    @property
    def provider_name(self) -> str:
        return "local"

    async def send(self, payload: NotificationPayload) -> NotificationResult:
        entry = {
            "id": f"local_{len(self._store)+1:06d}",
            "user_id": payload.recipient_user_id,
            "title": payload.title,
            "body": payload.body,
            "data": payload.data,
            "type": payload.notification_type,
            "priority": payload.priority,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        if len(self._store) >= self._max_stored:
            self._store = self._store[-self._max_stored // 2:]
        self._store.append(entry)
        logger.debug(
            "LocalNotificationProvider sent: user=%s title=%s",
            payload.recipient_user_id,
            payload.title,
        )
        return NotificationResult(
            success=True,
            provider=self.provider_name,
            status=ProviderStatus.OK,
            message_id=entry["id"],
        )

    async def health_check(self) -> ProviderStatus:
        return ProviderStatus.OK

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self._store)

    def clear(self) -> None:
        self._store.clear()


# ---------------------------------------------------------------------------
# External Provider Adapter (FCM / Web Push / APNs)
# ---------------------------------------------------------------------------
class ExternalNotificationProvider(NotificationProvider):
    """
    Adapter for external push notification services (FCM, Web Push, APNs).
    When credentials are absent, returns NOT_CONFIGURED without fabrication.
    Falls back to local provider for in-app delivery continuity.
    """

    def __init__(
        self,
        fcm_server_key: Optional[str] = None,
        fallback: Optional[NotificationProvider] = None,
    ):
        self._fcm_key = fcm_server_key
        self._fallback = fallback or LocalNotificationProvider()
        self._configured = bool(fcm_server_key)
        if not self._configured:
            logger.info(
                "ExternalNotificationProvider: FCM_SERVER_KEY not set. "
                "Status=NOT_CONFIGURED. Falling back to local provider."
            )

    @property
    def provider_name(self) -> str:
        return "external_fcm" if self._configured else "external_not_configured"

    async def send(self, payload: NotificationPayload) -> NotificationResult:
        if not self._configured:
            # Do NOT fabricate success — use local fallback
            fallback_result = await self._fallback.send(payload)
            return NotificationResult(
                success=False,
                provider=self.provider_name,
                status=ProviderStatus.NOT_CONFIGURED,
                error="FCM credentials not configured. Stored locally instead.",
                message_id=fallback_result.message_id,
            )

        # Attempt real FCM delivery
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    "https://fcm.googleapis.com/fcm/send",
                    headers={
                        "Authorization": f"key={self._fcm_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "to": f"/topics/user_{payload.recipient_user_id}",
                        "notification": {
                            "title": payload.title,
                            "body": payload.body,
                        },
                        "data": {k: str(v) for k, v in payload.data.items()},
                        "priority": "high" if payload.priority in ("HIGH", "CRITICAL") else "normal",
                    },
                )
                if resp.status_code == 200:
                    result_json = resp.json()
                    return NotificationResult(
                        success=True,
                        provider=self.provider_name,
                        status=ProviderStatus.OK,
                        message_id=str(result_json.get("message_id", "")),
                    )
                return NotificationResult(
                    success=False,
                    provider=self.provider_name,
                    status=ProviderStatus.DEGRADED,
                    error=f"FCM HTTP {resp.status_code}",
                )
        except Exception as exc:
            logger.error("ExternalNotificationProvider.send failed: %s", exc)
            return NotificationResult(
                success=False,
                provider=self.provider_name,
                status=ProviderStatus.ERROR,
                error=str(exc),
            )

    async def health_check(self) -> ProviderStatus:
        if not self._configured:
            return ProviderStatus.NOT_CONFIGURED
        return ProviderStatus.OK


# ---------------------------------------------------------------------------
# Notification Service — coordinates DB + provider + WebSocket
# ---------------------------------------------------------------------------
class NotificationService:
    """
    Creates in-app Notification rows, delivers via provider, and publishes
    real-time events via the WebSocket manager.
    """

    def __init__(self, provider: Optional[NotificationProvider] = None):
        self._provider = provider or LocalNotificationProvider()

    async def create_and_deliver(
        self,
        session: Any,  # AsyncSession
        user_id: str,
        title: str,
        body: str,
        notification_type: str = "SYSTEM_HEALTH",
        priority: str = "MEDIUM",
        data: Optional[Dict[str, Any]] = None,
        ws_manager: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        1. Persist Notification row in DB
        2. Send via notification provider
        3. Deliver via WebSocket if manager provided
        Returns a dict summary.
        """
        import uuid as _uuid
        from app.models.notification import Notification

        notif = Notification(
            user_id=_uuid.UUID(user_id),
            type=notification_type,
            title=title,
            body=body,
            data=data or {},
            is_read=False,
        )
        session.add(notif)
        await session.commit()
        await session.refresh(notif)

        # Provider delivery
        payload = NotificationPayload(
            recipient_user_id=user_id,
            title=title,
            body=body,
            data=data or {},
            notification_type=notification_type,
            priority=priority,
        )
        provider_result = await self._provider.send(payload)

        # WebSocket real-time delivery
        if ws_manager:
            from app.core.websocket_manager import build_event_envelope
            ws_event = build_event_envelope(
                "notification.new",
                str(notif.id),
                {
                    "notification_id": str(notif.id),
                    "title": title,
                    "body": body,
                    "type": notification_type,
                    "priority": priority,
                    "data": data or {},
                    "created_at": notif.created_at.isoformat(),
                },
            )
            await ws_manager.send_to_user(user_id, ws_event)

        return {
            "notification_id": str(notif.id),
            "provider": provider_result.provider,
            "provider_status": provider_result.status.value,
            "provider_success": provider_result.success,
        }

    async def get_provider_status(self) -> ProviderStatus:
        return await self._provider.health_check()


# ---------------------------------------------------------------------------
# Singleton — configured from environment
# ---------------------------------------------------------------------------
import os

_fcm_key = os.environ.get("FCM_SERVER_KEY", "")
_local_provider = LocalNotificationProvider()
_external_provider = ExternalNotificationProvider(
    fcm_server_key=_fcm_key or None,
    fallback=_local_provider,
)

notification_service = NotificationService(provider=_external_provider)
