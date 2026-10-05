import re
import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from connectors.schema import CanonicalRawEvent, ConnectorMetrics, ConnectorStatusEnum, CommonConnectorHealthReport

logger = logging.getLogger("skypulse.connectors")

# Regex to detect and sanitize any API keys, tokens, passwords in error strings
SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|secret|password|token|bearer|auth|authorization)[:=\s]+(['\"]?)[a-zA-Z0-9_\-\.]{8,}\2",
    r"sk-[a-zA-Z0-9_\-]{16,}",
    r"gsk_[a-zA-Z0-9_\-]{16,}",
    r"[0-9a-fA-F]{32,64}",
]


def sanitize_error_message(msg: str) -> str:
    """Removes secret tokens, credentials, and raw passwords from error strings."""
    if not msg:
        return ""
    sanitized = str(msg)
    for pat in SECRET_PATTERNS:
        sanitized = re.sub(pat, "[REDACTED]", sanitized)
    return sanitized


class BaseConnector(ABC):
    """
    Abstract Base Class for all SkyPulse weather ingestion connectors.
    Provides consistent lifecycle management, metrics collection, and status reporting.
    """

    def __init__(
        self,
        source_id: str,
        name: str,
        source_type: str,
        config: Optional[Dict[str, Any]] = None,
        is_demo: bool = False,
    ):
        self.source_id = source_id
        self.name = name
        self.source_type = source_type
        self.config = config or {}
        self.is_demo = is_demo
        self.is_running = False
        self.metrics = ConnectorMetrics()
        self.status = ConnectorStatusEnum.DEMO if is_demo else ConnectorStatusEnum.HEALTHY
        self.consecutive_failures = 0
        self.last_attempt_at: Optional[datetime] = None
        self.last_error_code: Optional[str] = None
        self.last_error_message: Optional[str] = None
        self.records_last_success: int = 0
        self.is_reachable: bool = False
        self.is_authenticated: Optional[bool] = None

    async def start(self) -> None:
        """Initialize connections, authentication, and start the connector."""
        self.is_running = True
        logger.info("Connector '%s' [%s] started.", self.name, self.source_id)

    async def stop(self) -> None:
        """Gracefully release connections, buffers, and stop polling."""
        self.is_running = False
        logger.info("Connector '%s' [%s] stopped.", self.name, self.source_id)

    @abstractmethod
    async def poll(self) -> List[CanonicalRawEvent]:
        """
        Poll external source or stream batch, returning standardized canonical raw events.
        Must handle its own transient errors and update metrics.
        """
        pass

    @abstractmethod
    def parse(self, raw_data: Any) -> CanonicalRawEvent:
        """Convert a single raw record/payload into a CanonicalRawEvent envelope."""
        pass

    async def health_check(self) -> ConnectorStatusEnum:
        """
        Inspect connectivity and configuration.
        Returns one of: HEALTHY, LIVE, DEGRADED, UNAVAILABLE, AUTH_ERROR, RATE_LIMITED, NOT_CONFIGURED, ERROR, DISABLED, DEMO.
        """
        if not self.is_running:
            return ConnectorStatusEnum.DISABLED
        if self.is_demo:
            return ConnectorStatusEnum.DEMO
        return self.status

    def record_success(self, count: int, latency_ms: float = 0.0) -> None:
        """Record successful poll telemetry."""
        now = datetime.now(timezone.utc)
        self.last_attempt_at = now
        self.consecutive_failures = 0
        self.records_last_success = count
        self.is_reachable = True
        if self.is_authenticated is None:
            self.is_authenticated = True
        self.last_error_code = None
        self.last_error_message = None
        self.metrics.records_fetched += count
        self.metrics.records_accepted += count
        self.metrics.last_successful_fetch = now
        self.metrics.processing_latency_ms = latency_ms
        if self.status not in (ConnectorStatusEnum.DEMO, ConnectorStatusEnum.NOT_CONFIGURED):
            self.status = ConnectorStatusEnum.HEALTHY

    def record_error(self, error: Exception | str, error_code: Optional[str] = None) -> None:
        """Record failure telemetry and update status with sanitized message."""
        now = datetime.now(timezone.utc)
        self.last_attempt_at = now
        self.consecutive_failures += 1
        raw_msg = str(error)
        clean_msg = sanitize_error_message(raw_msg)
        if error_code:
            self.last_error_code = error_code
        elif isinstance(error, Exception):
            self.last_error_code = type(error).__name__
        else:
            self.last_error_code = "CONNECTOR_ERROR"
        self.last_error_message = clean_msg
        self.metrics.last_error = clean_msg
        self.metrics.last_error_at = now
        self.metrics.records_rejected += 1
        if not self.is_demo and self.status != ConnectorStatusEnum.NOT_CONFIGURED:
            if self.consecutive_failures >= 3:
                self.status = ConnectorStatusEnum.UNAVAILABLE
            else:
                self.status = ConnectorStatusEnum.DEGRADED
        logger.error("Connector '%s' error [%s]: %s", self.name, self.last_error_code, clean_msg)


    def get_common_health(self) -> CommonConnectorHealthReport:
        """
        Exposes the standardized sanitized common health model (Phase 4).
        Never exposes API keys, tokens, or secret credentials.
        """
        is_healthy = self.status in (ConnectorStatusEnum.HEALTHY, ConnectorStatusEnum.LIVE)
        return CommonConnectorHealthReport(
            source=self.name,
            enabled=self.status != ConnectorStatusEnum.DISABLED,
            configured=self.status != ConnectorStatusEnum.NOT_CONFIGURED,
            reachable=self.is_reachable,
            authenticated=self.is_authenticated,
            healthy=is_healthy,
            status=self.status.value,
            last_success_at=self.metrics.last_successful_fetch,
            last_attempt_at=self.last_attempt_at,
            consecutive_failures=self.consecutive_failures,
            records_last_success=self.records_last_success,
            last_error_code=self.last_error_code,
            last_error_message=self.last_error_message,
        )

    def metadata(self) -> Dict[str, Any]:
        """Observability telemetry summary exposed to Admin API and health monitors."""
        return {
            "source_id": self.source_id,
            "name": self.name,
            "source_type": self.source_type,
            "is_demo": self.is_demo,
            "is_running": self.is_running,
            "status": self.status.value,
            "health": self.get_common_health().model_dump(),
            "metrics": self.metrics.model_dump(),
        }

