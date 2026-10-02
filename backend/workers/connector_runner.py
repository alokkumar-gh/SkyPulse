import asyncio
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.source import Source, ConnectorHealth
from app.models.enums import ConnectorStatus
from connectors.base import BaseConnector
from connectors.demo_connector import DemoConnector
from connectors.weather_api_connector import WeatherAPIConnector
from connectors.government_connector import GovernmentFeedConnector
from connectors.imd_connector import IMDConnector
from connectors.data_gov_connector import DataGovConnector
from connectors.rss_connector import RSSFeedConnector
from connectors.social_web_connector import social_web_connector
from connectors.search_discovery_connector import search_discovery_connector
from connectors.news_website_connector import news_website_connector
from connectors.indianapi_connector import indianapi_weather_connector
from connectors.openmeteo_connector import openmeteo_connector
from app.core.config import settings

from connectors.kafka_bus import kafka_producer, TOPIC_RAW


logger = logging.getLogger("skypulse.workers.connector_runner")


class ConnectorRunner:
    """
    Orchestrates execution of all registered connectors.
    Polls data sources and streams canonical raw events into skypulse.raw.
    Periodically updates connector health and ingestion statistics in PostgreSQL.
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.connectors: Dict[str, BaseConnector] = {}
        self.is_running = False
        self._poll_task: Optional[asyncio.Task] = None

        # Auto-register social media weather hashtag connector if enabled
        if getattr(settings, "SOCIAL_INGESTION_ENABLED", True):
            self.register_connector(social_web_connector)

        # Auto-register search discovery connector if enabled
        if getattr(settings, "SEARCH_DISCOVERY_ENABLED", True):
            self.register_connector(search_discovery_connector)

        # Auto-register news website connector if enabled
        if getattr(settings, "NEWS_INGESTION_ENABLED", True):
            self.register_connector(news_website_connector)

        # Auto-register IndianAPI connector if enabled
        if getattr(settings, "INDIANAPI_ENABLED", True):
            self.register_connector(indianapi_weather_connector)

        # Auto-register Open-Meteo connector if enabled
        if getattr(settings, "OPEN_METEO_ENABLED", True):
            self.register_connector(openmeteo_connector)

    def register_connector(self, connector: BaseConnector) -> None:
        self.connectors[connector.source_id] = connector

    async def start(self) -> None:
        self.is_running = True
        await kafka_producer.start()

        # Start all connectors
        for c in self.connectors.values():
            await c.start()

        self._poll_task = asyncio.create_task(self._run_loop())
        logger.info("ConnectorRunner started with %d active connectors", len(self.connectors))

    async def stop(self) -> None:
        self.is_running = False
        if self._poll_task:
            self._poll_task.cancel()
        for c in self.connectors.values():
            await c.stop()
        await kafka_producer.stop()
        logger.info("ConnectorRunner stopped")

    async def poll_once(self) -> int:
        """Poll each registered connector once and publish emitted events to Kafka."""
        total_emitted = 0
        for source_id, connector in self.connectors.items():
            if not connector.is_running:
                continue
            try:
                events = await connector.poll()
                for event in events:
                    await kafka_producer.publish(
                        TOPIC_RAW,
                        event,
                        key=event.external_id or event.ingestion_id,
                    )
                    total_emitted += 1
            except Exception as e:
                logger.error("Error polling connector %s: %s", connector.name, e)

        # Update health telemetry in database
        await self.sync_health_telemetry()
        return total_emitted

    async def sync_health_telemetry(self) -> None:
        """Syncs in-memory connector metrics to connector_health table in PostgreSQL."""
        if not self.session_factory:
            return

        try:
            async with self.session_factory() as session:
                for source_id_str, connector in self.connectors.items():
                    try:
                        s_uuid = uuid.UUID(source_id_str)
                    except ValueError:
                        continue

                    res = await session.execute(
                        select(ConnectorHealth).where(ConnectorHealth.source_id == s_uuid)
                    )
                    health = res.scalars().first()
                    if not health:
                        health = ConnectorHealth(source_id=s_uuid)
                        session.add(health)

                    health.status = connector.status.value
                    health.records_ingested_last_hour = connector.metrics.records_accepted
                    health.last_success_at = connector.metrics.last_successful_fetch
                    health.last_error = connector.metrics.last_error
                    health.last_error_at = connector.metrics.last_error_at
                    health.last_check_at = datetime.now(timezone.utc)

                await session.commit()
        except Exception as e:
            logger.debug("Failed to sync connector health to DB: %s", e)

    async def _run_loop(self) -> None:
        while self.is_running:
            try:
                await self.poll_once()
            except Exception as e:
                logger.error("ConnectorRunner loop failure: %s", e)
            await asyncio.sleep(5)
