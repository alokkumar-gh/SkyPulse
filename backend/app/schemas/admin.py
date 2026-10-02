"""Admin request/response schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class UserAdminResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UpdateUserRoleRequest(BaseModel):
    role: str = Field(description="One of: PUBLIC, CITIZEN, ANALYST, ADMIN, GOVERNMENT")


class AuditLogResponse(BaseModel):
    id: int
    created_at: datetime
    user_id: Optional[str] = None
    action_type: str
    entity_type: str
    entity_id: Optional[str] = None
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SystemHealthResponse(BaseModel):
    api_status: str
    database_status: str
    kafka_status: str
    redis_status: str
    opensearch_status: str
    neo4j_status: str
    ai_worker_status: str
    ingestion_rate_per_minute: int
    processing_queue_depth: int
    error_rate_last_hour: float
    connectors: List[Dict[str, Any]]
    ml_models: Optional[Dict[str, Any]] = None
    checked_at: datetime


class ClusterReportItem(BaseModel):
    id: str
    category: Optional[str] = None
    severity: Optional[int] = None
    source_type: Optional[str] = None
    event_time: Optional[datetime] = None
    location_state: Optional[str] = None
    location_district: Optional[str] = None
    normalized_text: Optional[str] = None
    is_duplicate: bool = False

    model_config = ConfigDict(from_attributes=True)


class DuplicateClusterResponse(BaseModel):
    id: str
    canonical_event_id: Optional[str] = None
    member_count: int
    state: Optional[str] = None
    created_at: Optional[datetime] = None
    reports: List[ClusterReportItem] = []

    model_config = ConfigDict(from_attributes=True)



class SplitClusterRequest(BaseModel):
    report_ids_to_remove: List[str]
    reason: str = Field(min_length=5, max_length=1000)


class MergeClustersRequest(BaseModel):
    primary_event_id: str
    secondary_event_id: str
    reason: str = Field(min_length=5, max_length=1000)


class FlaggedReportResponse(BaseModel):
    id: str
    category: Optional[str] = None
    sub_category: Optional[str] = None
    severity: Optional[int] = None
    confidence_score: Optional[float] = None
    status: str
    location_state: Optional[str] = None
    location_district: Optional[str] = None
    source_id: str
    source_name: Optional[str] = None
    raw_content: Optional[str] = None
    normalized_text: Optional[str] = None
    event_time: Optional[datetime] = None
    ingested_at: datetime
    is_duplicate: bool = False
    canonical_event_id: Optional[str] = None
    is_demo: bool = False

    model_config = ConfigDict(from_attributes=True)

