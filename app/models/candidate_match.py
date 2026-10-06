"""
Candidate Match model for competing hypotheses over detected change regions.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field
from app.models.enums import DataOrigin, Domain


class CandidateMatch(BaseModel):
    id: str
    analysis_id: str
    region_id: str
    candidate_domain: Domain
    physical_evidence: dict[str, Any] = Field(default_factory=dict)
    independent_evidence: dict[str, Any] = Field(default_factory=dict)
    contradicting_evidence: dict[str, Any] = Field(default_factory=dict)
    candidate_score: Optional[float] = None
    supported: bool
    notes: str
    is_demo: bool = True
    data_origin: DataOrigin = DataOrigin.SYNTHETIC_UI_FIXTURE
    disclaimer: str = "Synthetic development fixture — not an Earth observation result."
