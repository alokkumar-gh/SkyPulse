import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from connectors.schema import CanonicalRawEvent, ConnectorMetrics, ConnectorStatusEnum

logger = logging.getLogger("skypulse.connectors")


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
        Returns one of: HEALTHY, DEGRADED, NOT_CONFIGURED, ERROR, DISABLED, DEMO.
        """
        if not self.is_running:
            return ConnectorStatusEnum.DISABLED
        if self.is_demo:
            return ConnectorStatusEnum.DEMO
        return self.status

    def record_success(self, count: int, latency_ms: float = 0.0) -> None:
        """Record successful poll telemetry."""
        now = datetime.now(timezone.utc)
        self.metrics.records_fetched += count
        self.metrics.records_accepted += count
        self.metrics.last_successful_fetch = now
        self.metrics.processing_latency_ms = latency_ms
        if self.status not in (ConnectorStatusEnum.DEMO, ConnectorStatusEnum.NOT_CONFIGURED):
            self.status = ConnectorStatusEnum.HEALTHY

    def record_error(self, error: Exception | str) -> None:
        """Record failure telemetry and update status."""
        now = datetime.now(timezone.utc)
        error_msg = str(error)
        self.metrics.last_error = error_msg
        self.metrics.last_error_at = now
        self.metrics.records_rejected += 1
        if not self.is_demo:
            self.status = ConnectorStatusEnum.ERROR
        logger.error("Connector '%s' error: %s", self.name, error_msg)

    def metadata(self) -> Dict[str, Any]:
        """Observability telemetry summary exposed to Admin API and health monitors."""
        return {
            "source_id": self.source_id,
            "name": self.name,
            "source_type": self.source_type,
            "is_demo": self.is_demo,
            "is_running": self.is_running,
            "status": self.status.value,
            "metrics": self.metrics.model_dump(),
        }
