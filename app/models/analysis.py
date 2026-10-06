"""
Analysis model and structured quality metrics.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field
from app.models.enums import ClassificationStatus, DataOrigin, Domain, ObservationState


class AnalysisQuality(BaseModel):
    valid_pixel_fraction: float
    required_inputs_available: bool
    quality_gate_passed: bool
    notes: str


class Analysis(BaseModel):
    id: str
    aoi_id: str
    domain: Domain
    before_acquisition_id: Optional[str] = None
    after_acquisition_id: Optional[str] = None
    observation_state: ObservationState
    quality: AnalysisQuality
    measurements: dict[str, Any] = Field(default_factory=dict)
    manifest_id: str
    classification_status: ClassificationStatus
    final_classification: Optional[str] = None
    created_at: str
    is_demo: bool = True
    data_origin: DataOrigin = DataOrigin.SYNTHETIC_UI_FIXTURE
    disclaimer: str = "Synthetic development fixture — not an Earth observation result."
