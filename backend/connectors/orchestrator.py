"""
SkyPulse Unified Source Orchestration and Ingestion Telemetry Layer
====================================================================
Orchestrates multi-source weather data ingestion across all source families:
- IMD (India Meteorological Department)
- data.gov.in (Open Government Data Platform)
- GDACS / Government Feeds
- Social Media / Mastodon (#IMD & weather hashtags)
- Search Discovery (Web & Social public index)
- News Websites (Indian News Publishers & RSS/Atom feeds)
- Citizen Reports (Mobile/Web Observational Reports)
- Weather API / Demo Feeds

Provides national-level operational visibility, complete pipeline stage tracking:
SOURCE -> FETCH -> WEATHER RELEVANT -> INDIA VALID -> QUARANTINED -> DUPLICATES -> ACCEPTED -> CLASSIFIED -> VERIFIED -> WEATHER EVENT -> DWEG
"""

import asyncio
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.core.config import settings
from app.schemas.orchestration import (
    IngestionRunResponse,
    IngestionRunStatusEnum,
    PipelineStageTelemetry,
    SourceFamilySummaryItem,
    SourcePerformanceMetrics,
    UnifiedNationalOverviewResponse,
    UnifiedSourceStatusResponse,
)
from connectors.base import BaseConnector
from connectors.data_gov_connector import DataGovConnector
from connectors.demo_connector import DemoConnector
from connectors.government_connector import GovernmentFeedConnector
from connectors.imd_connector import IMDConnector
from connectors.kafka_bus import TOPIC_RAW, kafka_producer
from connectors.news_website_connector import news_website_connector
from connectors.rss_connector import RSSFeedConnector
from connectors.schema import CanonicalRawEvent, ConnectorMetrics, ConnectorStatusEnum
from connectors.search_discovery_connector import search_discovery_connector
from connectors.social_connector import SocialFeedConnector
from connectors.social_web_connector import social_web_connector
from connectors.weather_api_connector import WeatherAPIConnector
from connectors.indianapi_connector import IndianAPIWeatherConnector, indianapi_weather_connector
from connectors.openmeteo_connector import OpenMeteoConnector, openmeteo_connector
from connectors.weather_discovery import regional_discovery_connector

logger = logging.getLogger("skypulse.connectors.orchestrator")


class SourceFamilyEnum(str):
    IMD = "IMD"
    DATA_GOV = "DATA_GOV"
    GDACS = "GDACS"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    SEARCH_DISCOVERY = "SEARCH_DISCOVERY"
    NEWS_WEBSITE = "NEWS_WEBSITE"
    CITIZEN_REPORTS = "CITIZEN_REPORTS"
    WEATHER_API = "WEATHER_API"
    REGIONAL_DISCOVERY = "REGIONAL_DISCOVERY"
    DEMO = "DEMO"
    OTHER = "OTHER"


class RegisteredConnectorInfo:
    """Holds connector instance metadata, run history, and extended stage telemetry."""

    def __init__(
        self,
        connector: BaseConnector,
        display_name: str,
        source_family: str,
        polling_interval_seconds: int = 180,
    ):
        self.connector = connector
        self.display_name = display_name
        self.source_family = source_family
        self.polling_interval_seconds = polling_interval_seconds
        self.runs_history: deque[IngestionRunResponse] = deque(maxlen=50)

        # Extended stage counts not tracked in base connector
        self.classified_count: int = 0
        self.verified_count: int = 0
        self.total_processing_time_ms: float = 0.0
        self.total_runs_count: int = 0
        self.successful_runs_count: int = 0
        self.failed_runs_count: int = 0
        self.last_attempt_at: Optional[datetime] = None


class SourceOrchestratorService:
    """
    Central orchestration and telemetry service for all data ingestion sources.
    Tracks lifecycle, run execution, pipeline stages, and national health overview.
    """

    def __init__(self):
        self._registered: Dict[str, RegisteredConnectorInfo] = {}
        self._citizen_stage_telemetry = PipelineStageTelemetry()
        self._citizen_runs_history: deque[IngestionRunResponse] = deque(maxlen=50)
        self._init_default_connectors()

    def _init_default_connectors(self) -> None:
        """Discovers and registers all primary SkyPulse connectors."""
        # 1. IMD Connector
        try:
            imd_conn = IMDConnector(
                source_id="00000000-0000-0000-0000-000000000001",
                name="India Meteorological Department (IMD)",
                api_base_url=getattr(settings, "IMD_API_BASE_URL", ""),
                api_key=getattr(settings, "IMD_API_KEY", ""),
            )
            self.register_connector(
                connector=imd_conn,
                display_name="India Meteorological Department (IMD)",
                source_family=SourceFamilyEnum.IMD,
                polling_interval_seconds=getattr(settings, "IMD_POLL_INTERVAL_SECONDS", 300),
            )
        except Exception as e:
            logger.debug("Failed registering default IMD connector: %s", e)

        # 2. data.gov.in Connector
        try:
            datagov_conn = DataGovConnector(
                source_id="00000000-0000-0000-0000-000000000002",
                name="Open Government Data (data.gov.in)",
                api_key=getattr(settings, "DATA_GOV_API_KEY", ""),
            )
            self.register_connector(
                connector=datagov_conn,
                display_name="Open Government Data Platform India (data.gov.in)",
                source_family=SourceFamilyEnum.DATA_GOV,
                polling_interval_seconds=getattr(settings, "DATA_GOV_POLL_INTERVAL_SECONDS", 600),
            )
        except Exception as e:
            logger.debug("Failed registering default data.gov.in connector: %s", e)

        # 3. GDACS / Government Feed Connector
        try:
            gov_conn = GovernmentFeedConnector(
                source_id="00000000-0000-0000-0000-000000000005",
                name="Global Disaster Alert & Coordination System (GDACS)",
            )
            self.register_connector(
                connector=gov_conn,
                display_name="Global Disaster Alert (GDACS / MoES)",
                source_family=SourceFamilyEnum.GDACS,
                polling_interval_seconds=300,
            )
        except Exception as e:
            logger.debug("Failed registering default GDACS connector: %s", e)

        # 4. Social Web & Mastodon Connector
        try:
            self.register_connector(
                connector=social_web_connector,
                display_name="Social Media Weather Intelligence (Mastodon & Feeds)",
                source_family=SourceFamilyEnum.SOCIAL_MEDIA,
                polling_interval_seconds=getattr(settings, "SOCIAL_POLL_INTERVAL_SECONDS", 60),
            )
        except Exception as e:
            logger.debug("Failed registering default Social Web connector: %s", e)

        # 5. Search Discovery Ingestion Connector (Phase 1)
        try:
            self.register_connector(
                connector=search_discovery_connector,
                display_name="Search Discovery Weather Layer",
                source_family=SourceFamilyEnum.SEARCH_DISCOVERY,
                polling_interval_seconds=getattr(settings, "SEARCH_DISCOVERY_POLL_INTERVAL_SECONDS", 120),
            )
        except Exception as e:
            logger.debug("Failed registering default Search Discovery connector: %s", e)

        # 6. News Website Ingestion Connector
        try:
            self.register_connector(
                connector=news_website_connector,
                display_name="Indian News & Weather Publishers",
                source_family=SourceFamilyEnum.NEWS_WEBSITE,
                polling_interval_seconds=getattr(settings, "NEWS_POLL_INTERVAL_SECONDS", 180),
            )
        except Exception as e:
            logger.debug("Failed registering default News Website connector: %s", e)

        # 7. Weather API Connector
        try:
            w_api_conn = WeatherAPIConnector(
                source_id="00000000-0000-0000-0000-000000000006",
                name="Global Weather API Feed",
                api_key=getattr(settings, "OPENWEATHERMAP_KEY", "") or getattr(settings, "WEATHERAPI_KEY", ""),
            )
            self.register_connector(
                connector=w_api_conn,
                display_name="Global Meteorological APIs (OWM / WeatherAPI)",
                source_family=SourceFamilyEnum.WEATHER_API,
                polling_interval_seconds=600,
            )
        except Exception as e:
            logger.debug("Failed registering Weather API connector: %s", e)

        # 8. IndianAPI Third-Party Weather Connector
        try:
            indianapi_conn = IndianAPIWeatherConnector(
                source_id="00000000-0000-0000-0000-000000000007",
                name="IndianAPI Third-Party Weather Provider",
                api_key=getattr(settings, "INDIANAPI_API_KEY", ""),
            )
            self.register_connector(
                connector=indianapi_conn,
                display_name="IndianAPI Weather Service (Third-Party)",
                source_family=SourceFamilyEnum.WEATHER_API,
                polling_interval_seconds=getattr(settings, "INDIANAPI_POLL_INTERVAL_SECONDS", 600),
            )
        except Exception as e:
            logger.debug("Failed registering IndianAPI connector: %s", e)

        # 9. Open-Meteo Operational Weather Connector
        try:
            self.register_connector(
                connector=openmeteo_connector,
                display_name="Open-Meteo Operational Weather Provider",
                source_family=SourceFamilyEnum.WEATHER_API,
                polling_interval_seconds=getattr(settings, "OPEN_METEO_POLL_INTERVAL_SECONDS", 600),
            )
        except Exception as e:
            logger.debug("Failed registering Open-Meteo connector: %s", e)

        # 10. Regional Weather Intelligence Discovery Engine
        try:
            self.register_connector(
                connector=regional_discovery_connector,
                display_name="Regional Weather Intelligence Discovery Engine",
                source_family=SourceFamilyEnum.REGIONAL_DISCOVERY,
                polling_interval_seconds=getattr(settings, "REGIONAL_DISCOVERY_POLL_INTERVAL_SECONDS", 240),
            )
        except Exception as e:
            logger.debug("Failed registering Regional Discovery connector: %s", e)

    def register_connector(
        self,
        connector: BaseConnector,
        display_name: Optional[str] = None,
        source_family: Optional[str] = None,
        polling_interval_seconds: int = 180,
    ) -> None:
        """Dynamically registers or updates an ingestion connector."""
        family = source_family or self._infer_source_family(connector)
        name = display_name or connector.name
        self._registered[connector.source_id] = RegisteredConnectorInfo(
            connector=connector,
            display_name=name,
            source_family=family,
            polling_interval_seconds=polling_interval_seconds,
        )
        logger.info("Registered connector '%s' [%s] in family '%s'", name, connector.source_id, family)

    def unregister_connector(self, source_id: str) -> bool:
        """Unregisters a connector by source ID."""
        if source_id in self._registered:
            del self._registered[source_id]
            return True
        return False

    def get_connector_info(self, source_id: str) -> Optional[RegisteredConnectorInfo]:
        if source_id in self._registered:
            return self._registered[source_id]
        
        # Fallback to normalized name/slug lookup
        s_norm = source_id.lower().replace("-", "_").replace(" ", "_")
        for k, v in self._registered.items():
            k_norm = k.lower().replace("-", "_").replace(" ", "_")
            n_norm = v.connector.name.lower().replace("-", "_").replace(" ", "_")
            d_norm = v.display_name.lower().replace("-", "_").replace(" ", "_")
            if s_norm in (k_norm, n_norm, d_norm) or s_norm in n_norm:
                return v
        return None

    def get_all_registered(self) -> List[RegisteredConnectorInfo]:
        return list(self._registered.values())

    @staticmethod
    def _infer_source_family(connector: BaseConnector) -> str:
        name_lower = connector.name.lower()
        st_lower = connector.source_type.lower()
        if "imd" in name_lower or "imd" in st_lower:
            return SourceFamilyEnum.IMD
        if "data.gov" in name_lower or "datagov" in st_lower:
            return SourceFamilyEnum.DATA_GOV
        if "gdacs" in name_lower or "government" in st_lower:
            return SourceFamilyEnum.GDACS
        if "social" in name_lower or "mastodon" in name_lower or "social" in st_lower:
            return SourceFamilyEnum.SOCIAL_MEDIA
        if "search" in name_lower or "search_discovery" in st_lower:
            return SourceFamilyEnum.SEARCH_DISCOVERY
        if "news" in name_lower or "news_website" in st_lower:
            return SourceFamilyEnum.NEWS_WEBSITE
        if "citizen" in name_lower:
            return SourceFamilyEnum.CITIZEN_REPORTS
        if "weather_api" in st_lower or "weatherapi" in name_lower:
            return SourceFamilyEnum.WEATHER_API
        if "demo" in st_lower:
            return SourceFamilyEnum.DEMO
        return SourceFamilyEnum.OTHER

    # =========================================================================
    # Ingestion Run Execution & Lifecycle
    # =========================================================================

    async def execute_connector_run(self, source_id: str, session = None) -> IngestionRunResponse:
        """
        Executes an isolated ingestion run for a single registered connector.
        Guarantees fault isolation: failures in one connector cannot break others.
        Tags canonical events with ingestion_run_id for end-to-end traceability.
        """
        reg_info = self.get_connector_info(source_id)
        if not reg_info:
            return IngestionRunResponse(
                run_id=str(uuid.uuid4()),
                connector_id=source_id,
                display_name=f"Unknown ({source_id})",
                source_family=SourceFamilyEnum.OTHER,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_ms=0.0,
                status=IngestionRunStatusEnum.NOT_CONFIGURED,
                error_count=1,
                errors=[f"Connector '{source_id}' is not registered in orchestrator."],
            )

        connector = reg_info.connector
        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        reg_info.last_attempt_at = started_at
        reg_info.total_runs_count += 1

        # Check enabled/running status
        if not connector.is_running:
            try:
                await connector.start()
            except Exception as exc:
                reg_info.failed_runs_count += 1
                run_res = IngestionRunResponse(
                    run_id=run_id,
                    connector_id=source_id,
                    display_name=reg_info.display_name,
                    source_family=reg_info.source_family,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                    duration_ms=0.0,
                    status=IngestionRunStatusEnum.FAILED,
                    error_count=1,
                    errors=[f"Failed starting connector: {exc}"],
                )
                reg_info.runs_history.append(run_res)
                return run_res

        t0 = time.time()
        errors_captured: List[str] = []
        emitted_events: List[CanonicalRawEvent] = []

        try:
            raw_events = await connector.poll()
            for ev in raw_events:
                # Attach run traceability metadata
                if isinstance(ev, CanonicalRawEvent):
                    ev.raw_payload["ingestion_run_id"] = run_id
                    ev.raw_payload["source_family"] = reg_info.source_family
                    ev.raw_payload["connector_id"] = source_id

                    # Stream to raw topic if Kafka producer is available
                    try:
                        await kafka_producer.publish(
                            TOPIC_RAW,
                            ev,
                            key=ev.external_id or ev.ingestion_id,
                        )
                    except Exception:
                        pass

                    # Process through Unified Real-Time Ingestion Pipeline if database session provided
                    if session is not None:
                        try:
                            from app.services.unified_ingestion_service import unified_ingestion_pipeline
                            await unified_ingestion_pipeline.ingest_canonical_event(
                                raw_event=ev,
                                db=session,
                                ingestion_run_id=run_id,
                            )
                        except Exception as u_err:
                            logger.error("Unified pipeline processing failure for event %s: %s", ev.ingestion_id, u_err)

                    emitted_events.append(ev)

            reg_info.successful_runs_count += 1
        except Exception as exc:
            reg_info.failed_runs_count += 1
            errors_captured.append(str(exc))
            logger.error("Ingestion run failure on connector '%s': %s", reg_info.display_name, exc)

        completed_at = datetime.now(timezone.utc)
        duration_ms = round((time.time() - t0) * 1000, 2)
        reg_info.total_processing_time_ms += duration_ms

        # Calculate run-specific stage metrics from connector delta or emitted events
        m = connector.metrics
        run_status = IngestionRunStatusEnum.SUCCESS
        if errors_captured and len(emitted_events) == 0:
            run_status = IngestionRunStatusEnum.FAILED
        elif errors_captured and len(emitted_events) > 0:
            run_status = IngestionRunStatusEnum.PARTIAL
        elif connector.status == ConnectorStatusEnum.NOT_CONFIGURED:
            run_status = IngestionRunStatusEnum.NOT_CONFIGURED

        # Increment classified and verified estimations
        reg_info.classified_count += len(emitted_events)
        # Verified items estimate (e.g. government high-trust feeds)
        if reg_info.source_family in (SourceFamilyEnum.IMD, SourceFamilyEnum.GDACS, SourceFamilyEnum.DATA_GOV):
            reg_info.verified_count += len(emitted_events)

        run_res = IngestionRunResponse(
            run_id=run_id,
            connector_id=source_id,
            display_name=reg_info.display_name,
            source_family=reg_info.source_family,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            status=run_status,
            records_fetched=len(emitted_events) if not m.records_fetched else m.records_fetched,
            weather_relevant=len(emitted_events) if not m.weather_relevant else m.weather_relevant,
            india_valid=len(emitted_events) if not m.accepted_india else m.accepted_india,
            unknown_location=m.quarantined_unknown_location,
            quarantined=m.quarantined_foreign + m.quarantined_unknown_location,
            duplicates=m.duplicates,
            accepted=len(emitted_events) if not m.records_accepted else m.records_accepted,
            classified=len(emitted_events),
            verified=len(emitted_events) if reg_info.source_family == SourceFamilyEnum.IMD else 0,
            failed=len(errors_captured),
            error_count=len(errors_captured) + m.errors,
            errors=errors_captured,
        )

        reg_info.runs_history.append(run_res)

        # Persist completed run to PostgreSQL (isolated: failure never crashes connector execution)
        try:
            from app.services.ingestion_history_service import ingestion_history_service
            await ingestion_history_service.persist_ingestion_run(run_res, session=session)
        except Exception as persist_err:
            logger.error("Failed persisting run '%s' to database: %s", run_res.run_id, persist_err)

        # Broadcast realtime update if realtime gateway is available
        self._emit_realtime_run_completed(run_res)
        return run_res

    async def poll_all_connectors(self) -> List[IngestionRunResponse]:
        """Polls all active registered connectors concurrently with fault isolation."""
        tasks = []
        for s_id, info in self._registered.items():
            if info.connector.status != ConnectorStatusEnum.DISABLED:
                tasks.append(self.execute_connector_run(s_id))

        if not tasks:
            return []
        results = await asyncio.gather(*tasks, return_exceptions=True)
        runs: List[IngestionRunResponse] = []
        for r in results:
            if isinstance(r, IngestionRunResponse):
                runs.append(r)
        return runs

    def record_citizen_report_submission(self, raw_event: CanonicalRawEvent) -> None:
        """Records a real citizen submission into the unified ingestion telemetry."""
        self._citizen_stage_telemetry.records_fetched += 1
        self._citizen_stage_telemetry.weather_relevant += 1
        if raw_event.is_india_valid and not raw_event.is_quarantined:
            self._citizen_stage_telemetry.india_valid += 1
            self._citizen_stage_telemetry.accepted += 1
            self._citizen_stage_telemetry.classified += 1
        elif raw_event.is_quarantined:
            self._citizen_stage_telemetry.quarantined += 1

    # =========================================================================
    # Realtime Notification Helper
    # =========================================================================

    def _emit_realtime_run_completed(self, run: IngestionRunResponse) -> None:
        try:
            from workers.realtime_gateway import realtime_gateway
            asyncio.create_task(
                realtime_gateway.broadcast_system_event(
                    event_type="ingestion.run.completed",
                    data=run.model_dump(),
                )
            )
        except Exception:
            pass

    # =========================================================================
    # Telemetry and Overview Reporting
    # =========================================================================

    def get_source_status(self, source_id: str) -> Optional[UnifiedSourceStatusResponse]:
        """Returns unified operational status and performance metrics for a specific source."""
        info = self.get_connector_info(source_id)
        if not info:
            return None

        c = info.connector
        m = c.metrics

        # Stage Telemetry
        stage = PipelineStageTelemetry(
            records_fetched=m.records_fetched,
            weather_relevant=m.weather_relevant or m.records_accepted,
            india_valid=m.accepted_india or m.records_accepted,
            unknown_location=m.quarantined_unknown_location,
            quarantined=m.quarantined_foreign + m.quarantined_unknown_location,
            duplicates=m.duplicates,
            accepted=m.records_accepted,
            classified=info.classified_count or m.records_accepted,
            verified=info.verified_count or (m.records_accepted if info.source_family == SourceFamilyEnum.IMD else 0),
            failed=m.records_rejected + m.errors,
        )

        # Performance Rates
        total_runs = info.total_runs_count
        succ_runs = info.successful_runs_count
        failed_runs = info.failed_runs_count
        fetched = max(stage.records_fetched, 1)
        weather_rel = max(stage.weather_relevant, 1)
        accepted = max(stage.accepted, 1)

        perf = SourcePerformanceMetrics(
            fetch_success_rate=round(succ_runs / max(total_runs, 1), 4) if total_runs > 0 else 0.0,
            processing_success_rate=round(stage.accepted / fetched, 4) if stage.records_fetched > 0 else 0.0,
            weather_relevance_rate=round(stage.weather_relevant / fetched, 4) if stage.records_fetched > 0 else 0.0,
            india_validation_rate=round(stage.india_valid / weather_rel, 4) if stage.weather_relevant > 0 else 0.0,
            duplicate_rate=round(stage.duplicates / fetched, 4) if stage.records_fetched > 0 else 0.0,
            verification_rate=round(stage.verified / accepted, 4) if stage.accepted > 0 else 0.0,
            average_fetch_duration_ms=round(info.total_processing_time_ms / max(total_runs, 1), 2) if total_runs > 0 else 0.0,
            total_processing_time_ms=round(info.total_processing_time_ms, 2),
            total_runs_count=total_runs,
            successful_runs_count=succ_runs,
            failed_runs_count=failed_runs,
        )

        # Configuration status string
        cfg_status = "CONFIGURED"
        if c.status == ConnectorStatusEnum.NOT_CONFIGURED:
            cfg_status = "NOT_CONFIGURED"
        elif c.status == ConnectorStatusEnum.DISABLED:
            cfg_status = "DISABLED"
        elif c.is_demo:
            cfg_status = "DEMO"

        common_health = c.get_common_health()

        return UnifiedSourceStatusResponse(
            connector_id=c.source_id,
            display_name=info.display_name,
            source_family=info.source_family,
            source_type=c.source_type,
            enabled=c.status != ConnectorStatusEnum.DISABLED,
            configuration_status=cfg_status,
            health_status=c.status.value,
            polling_interval_seconds=info.polling_interval_seconds,
            last_attempt_at=info.last_attempt_at or c.last_attempt_at,
            last_success_at=m.last_successful_fetch,
            last_error_at=m.last_error_at,
            current_error=m.last_error,
            common_health=common_health,
            stage_telemetry=stage,
            performance=perf,
            recent_runs=list(info.runs_history),
        )

    def get_common_connector_health_reports(self) -> List[Any]:
        """Returns standard sanitized common connector health models across all connectors."""
        return [info.connector.get_common_health() for info in self._registered.values()]


    def get_source_health_matrix(self) -> List[UnifiedSourceStatusResponse]:
        """Returns health and status of all registered ingestion sources."""
        result = []
        for s_id in self._registered:
            st = self.get_source_status(s_id)
            if st:
                result.append(st)
        return result

    def get_recent_runs(self, connector_id: Optional[str] = None, limit: int = 50) -> List[IngestionRunResponse]:
        """Returns recent ingestion runs across all or a specific connector."""
        if connector_id:
            info = self.get_connector_info(connector_id)
            if not info:
                return []
            return list(info.runs_history)[-limit:]

        all_runs: List[IngestionRunResponse] = []
        for info in self._registered.values():
            all_runs.extend(list(info.runs_history))
        # Sort by started_at descending
        all_runs.sort(key=lambda r: r.started_at, reverse=True)
        return all_runs[:limit]

    def get_unified_overview(self) -> UnifiedNationalOverviewResponse:
        """
        Builds a national-level operational overview aggregating pipeline stages,
        health counts, performance metrics, and per-family comparison tables.
        """
        connectors_status = self.get_source_health_matrix()

        cfg_count = len(connectors_status)
        healthy = 0
        degraded = 0
        failed = 0
        disabled = 0
        not_cfg = 0

        # Global totals
        global_stage = PipelineStageTelemetry()
        total_runs = 0
        succ_runs = 0
        failed_runs = 0
        total_duration = 0.0

        family_map: Dict[str, SourceFamilySummaryItem] = {
            SourceFamilyEnum.IMD: SourceFamilySummaryItem(source_family=SourceFamilyEnum.IMD, display_name="India Meteorological Department (IMD)"),
            SourceFamilyEnum.DATA_GOV: SourceFamilySummaryItem(source_family=SourceFamilyEnum.DATA_GOV, display_name="Open Government Data (data.gov.in)"),
            SourceFamilyEnum.GDACS: SourceFamilySummaryItem(source_family=SourceFamilyEnum.GDACS, display_name="Global Disaster Alert (GDACS / MoES)"),
            SourceFamilyEnum.SOCIAL_MEDIA: SourceFamilySummaryItem(source_family=SourceFamilyEnum.SOCIAL_MEDIA, display_name="Social Media (#IMD & Weather Tags)"),
            SourceFamilyEnum.SEARCH_DISCOVERY: SourceFamilySummaryItem(source_family=SourceFamilyEnum.SEARCH_DISCOVERY, display_name="Search Discovery (Web & Social)"),
            SourceFamilyEnum.NEWS_WEBSITE: SourceFamilySummaryItem(source_family=SourceFamilyEnum.NEWS_WEBSITE, display_name="Indian News & Weather Publishers"),
            SourceFamilyEnum.CITIZEN_REPORTS: SourceFamilySummaryItem(
                source_family=SourceFamilyEnum.CITIZEN_REPORTS,
                display_name="Citizen & Observational Reports",
                records_fetched=self._citizen_stage_telemetry.records_fetched,
                weather_relevant=self._citizen_stage_telemetry.weather_relevant,
                india_valid=self._citizen_stage_telemetry.india_valid,
                accepted=self._citizen_stage_telemetry.accepted,
                classified=self._citizen_stage_telemetry.classified,
            ),
            SourceFamilyEnum.WEATHER_API: SourceFamilySummaryItem(source_family=SourceFamilyEnum.WEATHER_API, display_name="Global Weather APIs"),
        }

        for st in connectors_status:
            # Health classification
            h = st.health_status
            if h == ConnectorStatusEnum.HEALTHY.value:
                healthy += 1
            elif h == ConnectorStatusEnum.DEGRADED.value:
                degraded += 1
            elif h == ConnectorStatusEnum.ERROR.value:
                failed += 1
            elif h == ConnectorStatusEnum.DISABLED.value:
                disabled += 1
            elif h == ConnectorStatusEnum.NOT_CONFIGURED.value:
                not_cfg += 1

            # Accumulate global stage counters
            stg = st.stage_telemetry
            global_stage.records_fetched += stg.records_fetched
            global_stage.weather_relevant += stg.weather_relevant
            global_stage.india_valid += stg.india_valid
            global_stage.unknown_location += stg.unknown_location
            global_stage.quarantined += stg.quarantined
            global_stage.duplicates += stg.duplicates
            global_stage.accepted += stg.accepted
            global_stage.classified += stg.classified
            global_stage.verified += stg.verified
            global_stage.failed += stg.failed

            # Accumulate performance
            p = st.performance
            total_runs += p.total_runs_count
            succ_runs += p.successful_runs_count
            failed_runs += p.failed_runs_count
            total_duration += p.total_processing_time_ms

            # Family Summary Mapping
            fam = st.source_family
            if fam not in family_map:
                family_map[fam] = SourceFamilySummaryItem(source_family=fam, display_name=st.display_name)

            f_sum = family_map[fam]
            f_sum.connector_count += 1
            if st.enabled:
                f_sum.active_count += 1
            f_sum.records_fetched += stg.records_fetched
            f_sum.weather_relevant += stg.weather_relevant
            f_sum.india_valid += stg.india_valid
            f_sum.duplicates += stg.duplicates
            f_sum.accepted += stg.accepted
            f_sum.classified += stg.classified
            f_sum.verified += stg.verified
            if st.last_success_at:
                if not f_sum.last_success_at or st.last_success_at > f_sum.last_success_at:
                    f_sum.last_success_at = st.last_success_at

        # Add citizen report totals to global stage
        global_stage.records_fetched += self._citizen_stage_telemetry.records_fetched
        global_stage.weather_relevant += self._citizen_stage_telemetry.weather_relevant
        global_stage.india_valid += self._citizen_stage_telemetry.india_valid
        global_stage.accepted += self._citizen_stage_telemetry.accepted
        global_stage.classified += self._citizen_stage_telemetry.classified

        # Global performance calculations
        g_fetched = max(global_stage.records_fetched, 1)
        g_weather_rel = max(global_stage.weather_relevant, 1)
        g_accepted = max(global_stage.accepted, 1)

        global_perf = SourcePerformanceMetrics(
            fetch_success_rate=round(succ_runs / max(total_runs, 1), 4) if total_runs > 0 else 0.0,
            processing_success_rate=round(global_stage.accepted / g_fetched, 4) if global_stage.records_fetched > 0 else 0.0,
            weather_relevance_rate=round(global_stage.weather_relevant / g_fetched, 4) if global_stage.records_fetched > 0 else 0.0,
            india_validation_rate=round(global_stage.india_valid / g_weather_rel, 4) if global_stage.weather_relevant > 0 else 0.0,
            duplicate_rate=round(global_stage.duplicates / g_fetched, 4) if global_stage.records_fetched > 0 else 0.0,
            verification_rate=round(global_stage.verified / g_accepted, 4) if global_stage.accepted > 0 else 0.0,
            average_fetch_duration_ms=round(total_duration / max(total_runs, 1), 2) if total_runs > 0 else 0.0,
            total_processing_time_ms=round(total_duration, 2),
            total_runs_count=total_runs,
            successful_runs_count=succ_runs,
            failed_runs_count=failed_runs,
        )

        return UnifiedNationalOverviewResponse(
            timestamp=datetime.now(timezone.utc),
            total_sources_configured=cfg_count + 1,  # +1 for Citizen Reports
            total_sources_healthy=healthy + 1,
            total_sources_degraded=degraded,
            total_sources_failed=failed,
            total_sources_disabled=disabled,
            total_sources_not_configured=not_cfg,
            global_pipeline_telemetry=global_stage,
            global_performance=global_perf,
            source_family_summaries=list(family_map.values()),
            connectors=connectors_status,
        )

    # =========================================================================
    # Persistent Historical Telemetry Delegation
    # =========================================================================

    async def get_historical_runs(
        self,
        connector_id: Optional[str] = None,
        source_family: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
        session = None,
    ):
        from app.services.ingestion_history_service import ingestion_history_service
        return await ingestion_history_service.get_historical_runs(
            connector_id=connector_id,
            source_family=source_family,
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
            session=session,
        )

    async def get_historical_telemetry_aggregation(
        self,
        interval: str = "daily",
        connector_id: Optional[str] = None,
        source_family: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        session = None,
    ):
        from app.services.ingestion_history_service import ingestion_history_service
        return await ingestion_history_service.get_historical_telemetry_aggregation(
            interval=interval,
            connector_id=connector_id,
            source_family=source_family,
            start_date=start_date,
            end_date=end_date,
            session=session,
        )

    async def get_historical_source_comparison(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        session = None,
    ):
        from app.services.ingestion_history_service import ingestion_history_service
        return await ingestion_history_service.get_historical_source_comparison(
            start_date=start_date,
            end_date=end_date,
            session=session,
        )

    async def get_historical_performance_summary(
        self,
        connector_id: Optional[str] = None,
        source_family: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        session = None,
    ):
        from app.services.ingestion_history_service import ingestion_history_service
        return await ingestion_history_service.get_historical_performance_summary(
            connector_id=connector_id,
            source_family=source_family,
            start_date=start_date,
            end_date=end_date,
            session=session,
        )

    async def prune_historical_records(self, retention_days: int = 90, session = None):
        from app.services.ingestion_history_service import ingestion_history_service
        return await ingestion_history_service.prune_historical_records(retention_days=retention_days, session=session)


# Global singleton orchestrator
source_orchestrator = SourceOrchestratorService()
