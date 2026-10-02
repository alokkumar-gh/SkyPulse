"""
Shared Pydantic schemas: pagination envelope, error response, common types.
"""
from typing import Generic, List, Optional, TypeVar, Any, Dict
from pydantic import BaseModel, ConfigDict
import math

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated envelope used by all list endpoints."""
    total: int
    page: int
    per_page: int
    pages: int
    results: List[T]

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def build(cls, items: List[T], total: int, page: int, per_page: int) -> "PaginatedResponse[T]":
        pages = math.ceil(total / per_page) if per_page > 0 else 0
        return cls(total=total, page=page, per_page=per_page, pages=pages, results=items)


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Dict[str, Any] = {}


class LocationSchema(BaseModel):
    """Embedded location object used in reports and events."""
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    confidence: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
