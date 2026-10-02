"""Analytics response schemas."""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class CategoryCounts(BaseModel):
    RAINFALL: int = 0
    FLOODING: int = 0
    THUNDERSTORM: int = 0
    HEATWAVE: int = 0
    FOG: int = 0
    DUST_STORM: int = 0
    STRONG_WINDS: int = 0


class VerificationCounts(BaseModel):
    VERIFIED: int = 0
    LIKELY: int = 0
    UNVERIFIED: int = 0
    CONTRADICTED: int = 0
    REQUIRES_REVIEW: int = 0


class SeverityCounts(BaseModel):
    s1: int = Field(0, alias="1")
    s2: int = Field(0, alias="2")
    s3: int = Field(0, alias="3")
    s4: int = Field(0, alias="4")

    model_config = ConfigDict(populate_by_name=True)


class StatePeriod(BaseModel):
    state: str
    event_count: int


class NationalAnalytics(BaseModel):
    period: Dict[str, str]
    total_events: int
    active_events: int
    total_reports: int
    by_category: Dict[str, int]
    by_verification_status: Dict[str, int]
    by_severity: Dict[str, int]
    anomalous_events: int
    top_states: List[StatePeriod]


class StateAnalytics(BaseModel):
    state: str
    period: Dict[str, str]
    total_events: int
    active_events: int
    total_reports: int
    by_category: Dict[str, int]
    by_verification_status: Dict[str, int]
    by_severity: Dict[str, int]
    top_districts: List[Dict]


class TimeseriesPoint(BaseModel):
    timestamp: datetime
    value: float


class TimeseriesResponse(BaseModel):
    metric: str
    interval: str
    series: List[TimeseriesPoint]

