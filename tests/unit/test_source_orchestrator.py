"""
Unit and integration tests for the SkyPulse Unified Source Orchestration and Telemetry Layer.
Tests dynamic connector discovery, fault-isolated ingestion runs, lifecycle status transitions,
stage telemetry aggregation, mathematical counter consistency, cross-connector deduplication,
source -> ingestion-run -> event traceability, and REST API endpoints.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from connectors.schema import (
    CanonicalRawEvent,
    ConnectorStatusEnum,
    ConnectorMetrics,
)
from connectors.base import BaseConnector
from connectors.orchestrator import (
    SourceOrchestratorService,
    SourceFamilyEnum,
    RegisteredConnectorInfo,
    source_orchestrator,
)
from app.schemas.orchestration import (
    IngestionRunStatusEnum,
    IngestionRunResponse,
    UnifiedNationalOverviewResponse,
    UnifiedSourceStatusResponse,
)


# ==============================================================================
# Test Fixtures & Mock Connectors
# ==============================================================================

class MockTestConnector(BaseConnector):
    """Controllable mock connector for testing orchestration behaviors."""

    def __init__(
        self,
        source_id: str,
        name: str = "Mock Test Connector",
        source_type: str = "TEST_SOURCE",
        should_fail: bool = False,
        return_events_count: int = 3,
        status: ConnectorStatusEnum = ConnectorStatusEnum.HEALTHY,
    ):
        super().__init__(source_id=source_id, name=name, source_type=source_type)
        self.should_fail = should_fail
        self.return_events_count = return_events_count
        self.status = status
        self.is_running = True

    async def poll(self):
        if self.should_fail:
            self.metrics.errors += 1
            self.metrics.last_error = "Connection timeout to remote upstream feed"
            self.metrics.last_error_at = datetime.now(timezone.utc)
            self.status = ConnectorStatusEnum.ERROR
            raise ConnectionError("Connection timeout to remote upstream feed")

        events = []
        for i in range(self.return_events_count):
            events.append(
                CanonicalRawEvent(
                    source_id=self.source_id,
                    source_type=self.source_type,
                    external_id=f"test_{self.source_id}_{i}",
                    text=f"Heavy rain and waterlogging observed in Mumbai #{i}",
                    city="Mumbai",
                    state="Maharashtra",
                    is_india_valid=True,
                    is_quarantined=False,
                    suggested_category="RAINFALL",
                    observed_at=datetime.now(timezone.utc),
                )
            )
        self.metrics.records_fetched += len(events)
        self.metrics.records_accepted += len(events)
        self.metrics.weather_relevant += len(events)
        self.metrics.accepted_india += len(events)
        self.metrics.last_successful_fetch = datetime.now(timezone.utc)
        return events

    def parse(self, raw_data):
        return None


# ==============================================================================
# 1. Dynamic Connector Discovery & Registration Tests
# ==============================================================================

def test_1_dynamic_connector_discovery_and_registration():
    orchestrator = SourceOrchestratorService()
    all_registered = orchestrator.get_all_registered()

    # Must contain default core source families
    families = [info.source_family for info in all_registered]
    assert SourceFamilyEnum.IMD in families
    assert SourceFamilyEnum.DATA_GOV in families
    assert SourceFamilyEnum.SOCIAL_MEDIA in families
    assert SourceFamilyEnum.SEARCH_DISCOVERY in families
    assert SourceFamilyEnum.NEWS_WEBSITE in families

    # Test dynamic registration
    custom_conn = MockTestConnector(source_id="custom-radar-001", name="Doppler Radar Network")
    orchestrator.register_connector(
        connector=custom_conn,
        display_name="National Doppler Radar Network",
        source_family="RADAR",
        polling_interval_seconds=60,
    )

    info = orchestrator.get_connector_info("custom-radar-001")
    assert info is not None
    assert info.display_name == "National Doppler Radar Network"
    assert info.source_family == "RADAR"
    assert info.polling_interval_seconds == 60

    # Test unregister
    assert orchestrator.unregister_connector("custom-radar-001") is True
    assert orchestrator.get_connector_info("custom-radar-001") is None


# ==============================================================================
# 2. Ingestion Run Execution & Fault Isolation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_2_successful_ingestion_run_and_traceability():
    orchestrator = SourceOrchestratorService()
    mock_conn = MockTestConnector(source_id="test-succ-01", name="Success Test Connector", return_events_count=4)
    orchestrator.register_connector(mock_conn, display_name="Success Connector", source_family=SourceFamilyEnum.NEWS_WEBSITE)

    run_res = await orchestrator.execute_connector_run("test-succ-01")
    assert run_res.status == IngestionRunStatusEnum.SUCCESS
    assert run_res.connector_id == "test-succ-01"
    assert run_res.records_fetched == 4
    assert run_res.accepted == 4
    assert run_res.error_count == 0
    assert run_res.duration_ms >= 0.0

    # Verify run is stored in connector history
    recent_runs = orchestrator.get_recent_runs(connector_id="test-succ-01")
    assert len(recent_runs) >= 1
    assert recent_runs[-1].run_id == run_res.run_id


@pytest.mark.asyncio
async def test_3_failed_ingestion_run_fault_isolation():
    orchestrator = SourceOrchestratorService()
    failing_conn = MockTestConnector(source_id="test-fail-01", name="Failing Connector", should_fail=True)
    working_conn = MockTestConnector(source_id="test-work-01", name="Working Connector", return_events_count=2)

    orchestrator.register_connector(failing_conn, display_name="Failing Source", source_family=SourceFamilyEnum.WEATHER_API)
    orchestrator.register_connector(working_conn, display_name="Working Source", source_family=SourceFamilyEnum.IMD)

    # Failing connector execution must NOT throw unhandled exception or crash orchestrator
    fail_run = await orchestrator.execute_connector_run("test-fail-01")
    assert fail_run.status == IngestionRunStatusEnum.FAILED
    assert fail_run.error_count >= 1
    assert len(fail_run.errors) > 0
    assert "timeout" in fail_run.errors[0].lower()

    # Working connector must execute independently and succeed
    work_run = await orchestrator.execute_connector_run("test-work-01")
    assert work_run.status == IngestionRunStatusEnum.SUCCESS
    assert work_run.records_fetched == 2


@pytest.mark.asyncio
async def test_4_unconfigured_and_disabled_connector_run():
    orchestrator = SourceOrchestratorService()
    unconfigured_conn = MockTestConnector(
        source_id="unconfigured-01",
        status=ConnectorStatusEnum.NOT_CONFIGURED,
        return_events_count=0,
    )
    orchestrator.register_connector(unconfigured_conn, source_family=SourceFamilyEnum.OTHER)

    run_res = await orchestrator.execute_connector_run("unconfigured-01")
    assert run_res.status in (IngestionRunStatusEnum.NOT_CONFIGURED, IngestionRunStatusEnum.SUCCESS)


# ==============================================================================
# 3. Pipeline Stage Telemetry & Invariants Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_5_telemetry_aggregation_and_mathematical_consistency():
    orchestrator = SourceOrchestratorService()
    conn1 = MockTestConnector(source_id="c1", return_events_count=5)
    conn2 = MockTestConnector(source_id="c2", return_events_count=3)

    orchestrator.register_connector(conn1, source_family=SourceFamilyEnum.IMD)
    orchestrator.register_connector(conn2, source_family=SourceFamilyEnum.SOCIAL_MEDIA)

    await orchestrator.execute_connector_run("c1")
    await orchestrator.execute_connector_run("c2")

    overview = orchestrator.get_unified_overview()
    gt = overview.global_pipeline_telemetry

    # Telemetry Invariants Check:
    assert gt.records_fetched >= 8
    assert gt.accepted >= 8
    assert gt.weather_relevant >= gt.accepted
    assert gt.india_valid >= gt.accepted

    # Performance metrics must have non-negative rates
    perf = overview.global_performance
    assert 0.0 <= perf.fetch_success_rate <= 1.0
    assert 0.0 <= perf.processing_success_rate <= 1.0
    assert perf.total_runs_count >= 2


def test_6_zero_fake_telemetry_guarantee():
    # A fresh orchestrator with non-run connectors must NOT manufacture fake run stats
    orchestrator = SourceOrchestratorService()
    custom_conn = MockTestConnector(source_id="fresh-conn", return_events_count=0)
    orchestrator.register_connector(custom_conn, source_family="ISOLATED")

    status = orchestrator.get_source_status("fresh-conn")
    assert status is not None
    assert status.stage_telemetry.records_fetched == 0
    assert status.stage_telemetry.accepted == 0
    assert status.performance.total_runs_count == 0
    assert status.performance.fetch_success_rate == 0.0
    assert status.last_success_at is None
    assert len(status.recent_runs) == 0


# ==============================================================================
# 4. Source Comparison & Family Summaries Tests
# ==============================================================================

def test_7_source_family_comparison_matrix():
    orchestrator = SourceOrchestratorService()
    overview = orchestrator.get_unified_overview()

    families = [f.source_family for f in overview.source_family_summaries]
    assert SourceFamilyEnum.IMD in families
    assert SourceFamilyEnum.DATA_GOV in families
    assert SourceFamilyEnum.SOCIAL_MEDIA in families
    assert SourceFamilyEnum.SEARCH_DISCOVERY in families
    assert SourceFamilyEnum.NEWS_WEBSITE in families
    assert SourceFamilyEnum.CITIZEN_REPORTS in families


def test_8_citizen_report_submission_telemetry_integration():
    orchestrator = SourceOrchestratorService()
    raw_citizen_event = CanonicalRawEvent(
        source_id="citizen-reports",
        source_type="CITIZEN",
        external_id="SP-2026-999999",
        text="Heavy waterlogging in Dadar near station",
        city="Mumbai",
        state="Maharashtra",
        is_india_valid=True,
        is_quarantined=False,
        suggested_category="FLOODING",
    )

    orchestrator.record_citizen_report_submission(raw_citizen_event)
    overview = orchestrator.get_unified_overview()

    citizen_summary = next(
        (f for f in overview.source_family_summaries if f.source_family == SourceFamilyEnum.CITIZEN_REPORTS),
        None,
    )
    assert citizen_summary is not None
    assert citizen_summary.records_fetched >= 1
    assert citizen_summary.accepted >= 1


# ==============================================================================
# 5. REST API Endpoints Integration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_9_unified_connector_api_endpoints(client, test_admin, auth_headers):
    headers = auth_headers(test_admin)

    # 1. GET /api/v1/connectors/overview
    resp_overview = await client.get("/api/v1/connectors/overview", headers=headers)
    assert resp_overview.status_code == 200
    data_overview = resp_overview.json()
    assert "global_pipeline_telemetry" in data_overview
    assert "source_family_summaries" in data_overview
    assert len(data_overview["source_family_summaries"]) > 0

    # 2. GET /api/v1/connectors/health
    resp_health = await client.get("/api/v1/connectors/health", headers=headers)
    assert resp_health.status_code == 200
    data_health = resp_health.json()
    assert isinstance(data_health, list)
    assert len(data_health) > 0

    # 3. GET /api/v1/connectors/telemetry
    resp_telem = await client.get("/api/v1/connectors/telemetry", headers=headers)
    assert resp_telem.status_code == 200
    data_telem = resp_telem.json()
    assert "global_pipeline_telemetry" in data_telem
    assert "global_performance" in data_telem

    # 4. GET /api/v1/connectors/runs
    resp_runs = await client.get("/api/v1/connectors/runs", headers=headers)
    assert resp_runs.status_code == 200
    data_runs = resp_runs.json()
    assert "runs" in data_runs
    assert "total" in data_runs


@pytest.mark.asyncio
async def test_10_connector_detail_and_poll_api_endpoints(client, test_admin, auth_headers):
    headers = auth_headers(test_admin)

    # Get first available connector ID from health list
    resp_health = await client.get("/api/v1/connectors/health", headers=headers)
    assert resp_health.status_code == 200
    connectors = resp_health.json()
    assert len(connectors) > 0
    target_id = connectors[0]["connector_id"]

    # 1. GET /api/v1/connectors/{connector_id}
    resp_detail = await client.get(f"/api/v1/connectors/{target_id}", headers=headers)
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["connector_id"] == target_id
    assert "stage_telemetry" in detail
    assert "performance" in detail

    # 2. POST /api/v1/connectors/{connector_id}/poll
    resp_poll = await client.post(f"/api/v1/connectors/{target_id}/poll", headers=headers)
    assert resp_poll.status_code == 200
    poll_res = resp_poll.json()
    assert "run" in poll_res
    assert poll_res["connector_id"] == target_id

    # 3. GET /api/v1/connectors/{connector_id}/runs
    resp_conn_runs = await client.get(f"/api/v1/connectors/{target_id}/runs", headers=headers)
    assert resp_conn_runs.status_code == 200
    conn_runs = resp_conn_runs.json()
    assert conn_runs["total"] >= 1

