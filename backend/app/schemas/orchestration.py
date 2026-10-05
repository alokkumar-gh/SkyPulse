"""
Pydantic schemas for Unified Source Ingestion Orchestration and Telemetry.
Provides national-level operational visibility, pipeline stage tracking,
source health matrix, and ingestion run lifecycle reporting.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class IngestionRunStatusEnum(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    DISABLED = "DISABLED"


class SourceFamilyEnum(str, Enum):
    IMD = "IMD"
    DATA_GOV = "DATA_GOV"
    GDACS = "GDACS"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    SEARCH_DISCOVERY = "SEARCH_DISCOVERY"
    NEWS_WEBSITE = "NEWS_WEBSITE"
    CITIZEN_REPORTS = "CITIZEN_REPORTS"
    WEATHER_API = "WEATHER_API"
    DEMO = "DEMO"
    OTHER = "OTHER"


class IngestionRunResponse(BaseModel):
    run_id: str
    connector_id: str
    display_name: str
    source_family: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    status: IngestionRunStatusEnum
    records_fetched: int = 0
    weather_relevant: int = 0
    india_valid: int = 0
    unknown_location: int = 0
    quarantined: int = 0
    duplicates: int = 0
    accepted: int = 0
    classified: int = 0
    verified: int = 0
    failed: int = 0
    error_count: int = 0
    errors: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PipelineStageTelemetry(BaseModel):
    """Cumulative counts across processing stages from fetch to DWEG integration."""
    records_fetched: int = 0
    weather_relevant: int = 0
    india_valid: int = 0
    unknown_location: int = 0
    quarantined: int = 0
    duplicates: int = 0
    accepted: int = 0
    classified: int = 0
    verified: int = 0
    failed: int = 0

    model_config = ConfigDict(from_attributes=True)


class SourcePerformanceMetrics(BaseModel):
    fetch_success_rate: float = 0.0
    processing_success_rate: float = 0.0
    weather_relevance_rate: float = 0.0
    india_validation_rate: float = 0.0
    duplicate_rate: float = 0.0
    verification_rate: float = 0.0
    average_fetch_duration_ms: float = 0.0
    total_processing_time_ms: float = 0.0
    total_runs_count: int = 0
    successful_runs_count: int = 0
    failed_runs_count: int = 0

    model_config = ConfigDict(from_attributes=True)


from connectors.schema import CommonConnectorHealthReport


class UnifiedSourceStatusResponse(BaseModel):
    connector_id: str
    display_name: str
    source_family: str
    source_type: str
    enabled: bool
    configuration_status: str
    health_status: str
    polling_interval_seconds: int = 0
    last_attempt_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    current_error: Optional[str] = None
    common_health: Optional[CommonConnectorHealthReport] = None
    stage_telemetry: PipelineStageTelemetry
    performance: SourcePerformanceMetrics
    recent_runs: List[IngestionRunResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)



class SourceFamilySummaryItem(BaseModel):
    source_family: str
    display_name: str
    connector_count: int = 0
    active_count: int = 0
    health_status: str = "HEALTHY"
    records_fetched: int = 0
    weather_relevant: int = 0
    india_valid: int = 0
    duplicates: int = 0
    accepted: int = 0
    classified: int = 0
    verified: int = 0
    last_success_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UnifiedNationalOverviewResponse(BaseModel):
    title: str = "SkyPulse National Weather Ingestion Orchestration"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_sources_configured: int = 0
    total_sources_healthy: int = 0
    total_sources_degraded: int = 0
    total_sources_failed: int = 0
    total_sources_disabled: int = 0
    total_sources_not_configured: int = 0
    global_pipeline_telemetry: PipelineStageTelemetry
    global_performance: SourcePerformanceMetrics
    source_family_summaries: List[SourceFamilySummaryItem] = Field(default_factory=list)
    connectors: List[UnifiedSourceStatusResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class IngestionRunsListResponse(BaseModel):
    total: int
    runs: List[IngestionRunResponse] = Field(default_factory=list)


class TriggerRunResponse(BaseModel):
    connector_id: str
    display_name: str
    run: IngestionRunResponse
    message: str


# ==============================================================================
# Persistent Historical Telemetry & Aggregation Schemas
# ==============================================================================

class HistoricalAggregationIntervalEnum(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class HistoricalTelemetryBucket(BaseModel):
    """Aggregated telemetry metrics for a specific time interval bucket."""
    bucket_start: datetime
    bucket_end: datetime
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    records_fetched: int = 0
    weather_relevant: int = 0
    india_valid: int = 0
    quarantined: int = 0
    duplicates: int = 0
    accepted: int = 0
    classified: int = 0
    verified: int = 0
    failed: int = 0
    error_count: int = 0
    fetch_success_rate: float = 0.0
    processing_success_rate: float = 0.0
    weather_relevance_rate: float = 0.0
    india_validation_rate: float = 0.0
    duplicate_rate: float = 0.0
    verification_rate: float = 0.0
    average_duration_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class HistoricalTelemetryResponse(BaseModel):
    interval: str
    connector_id: Optional[str] = None
    source_family: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    total_buckets: int = 0
    buckets: List[HistoricalTelemetryBucket] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class HistoricalSourceComparisonRow(BaseModel):
    source_family: str
    display_name: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    records_fetched: int = 0
    weather_relevant: int = 0
    india_valid: int = 0
    duplicates: int = 0
    accepted: int = 0
    classified: int = 0
    verified: int = 0
    first_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class HistoricalSourceComparisonResponse(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    total_sources: int = 0
    sources: List[HistoricalSourceComparisonRow] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class HistoricalPerformanceSummaryResponse(BaseModel):
    connector_id: Optional[str] = None
    source_family: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metrics: SourcePerformanceMetrics
    stage_totals: PipelineStageTelemetry

    model_config = ConfigDict(from_attributes=True)


class PruneHistoryResponse(BaseModel):
    pruned_records_count: int
    retention_days: int
    cutoff_date: datetime
    message: str

