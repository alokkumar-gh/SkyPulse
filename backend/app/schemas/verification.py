"""Verification request/response schemas."""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

VALID_VERIFICATION_STATUSES = {
    "VERIFIED", "LIKELY", "UNVERIFIED", "CONTRADICTED", "REQUIRES_REVIEW"
}


class VerificationEvidenceItem(BaseModel):
    evidence_type: str
    source_name: Optional[str] = None
    description: Optional[str] = None
    weight_contribution: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class VerificationResult(BaseModel):
    event_id: str
    status: str
    confidence_score: Optional[float] = None
    explanation_text: Optional[str] = None
    evidence_items: List[VerificationEvidenceItem] = []
    signal_scores: Optional[Dict[str, float]] = None
    method: Optional[str] = None
    is_manual_override: bool = False
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ManualOverrideRequest(BaseModel):
    status: str
    reason: str = Field(min_length=5, max_length=1000)

    def validate_status(self) -> None:
        if self.status not in VALID_VERIFICATION_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_VERIFICATION_STATUSES)}")


class VerificationQueueItem(BaseModel):
    event_id: str
    category: Optional[str] = None
    severity: Optional[int] = None
    confidence_score: Optional[float] = None
    verification_status: Optional[str] = None
    state: Optional[str] = None
    first_reported_at: Optional[datetime] = None
    evidence_count: int = 0

    model_config = ConfigDict(from_attributes=True)
