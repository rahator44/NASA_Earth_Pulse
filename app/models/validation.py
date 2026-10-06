"""
ValidationResult model representing algorithmic provenance and accuracy benchmarks.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field
from app.models.enums import DataOrigin, ValidationStatus


class ValidationResult(BaseModel):
    id: str
    analysis_id: str
    status: ValidationStatus
    number_of_independent_events: int = 0
    calibration_event_id: Optional[str] = None
    validation_event_ids: list[str] = Field(default_factory=list)
    independent_validation: bool = False
    reference_dataset: Optional[str] = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    is_demo: bool = True
    data_origin: DataOrigin = DataOrigin.SYNTHETIC_UI_FIXTURE
    disclaimer: str = "Synthetic development fixture — not an Earth observation result."
