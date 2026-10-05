"""Map / geospatial response schemas (GeoJSON FeatureCollection)."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GeoJSONGeometry(BaseModel):
    type: str
    coordinates: List[Any]


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    id: Optional[str] = None
    geometry: GeoJSONGeometry
    properties: Dict[str, Any]


class MapCoverageSummary(BaseModel):
    states_represented: int = 0
    total_states: int = 36
    districts_represented: int = 0
    total_districts: int = 788
    current_observations_count: int = 0
    active_warnings_count: int = 0
    active_events_count: int = 0
    fresh_news_count: int = 0
    state_observation_coverage: float = 0.0
    state_event_coverage: float = 0.0
    coverage_updated_at: Optional[str] = None


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature] = Field(default_factory=list)
    server_time: Optional[str] = None
    generated_at: Optional[str] = None
    window: Optional[str] = None
    total_features: Optional[int] = None
    total_mapped: Optional[int] = None
    total_polygons: Optional[int] = None
    hours: Optional[int] = None
    coverage: Optional[Dict[str, Any]] = None
    signals_by_type: Optional[Dict[str, int]] = None
    points: Optional[List[Dict[str, Any]]] = None
    polygons: Optional[List[Dict[str, Any]]] = None
