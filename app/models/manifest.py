"""
AnalysisManifest model tracking complete provenance and processing parameters.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field
from app.models.enums import DataOrigin, Domain, ProductMaturity


class AnalysisManifest(BaseModel):
    manifest_id: str
    analysis_id: str
    aoi_id: str
    domain: Domain
    before_acquisition_id: Optional[str] = None
    after_acquisition_id: Optional[str] = None
    comparison_policy: str
    reference_acquisition_id: Optional[str] = None
    track: int
    frame: int
    orbit_direction: str
    mode: str
    polarizations: list[str] = Field(default_factory=list)
    maturity: ProductMaturity = ProductMaturity.PROVISIONAL
    crid: str
    pipeline_version: str
    code_version: str
    quality_parameters: dict[str, Any] = Field(default_factory=dict)
    detection_parameters: dict[str, Any] = Field(default_factory=dict)
    threshold_selection_method: Optional[str] = None
    reference_area: Optional[str] = None
    validation_reference: Optional[str] = None
    calibration_event_id: Optional[str] = None
    validation_event_ids: list[str] = Field(default_factory=list)
    independent_validation: bool = False
    created_at: str

    # Optional wildfire-specific parameters (nullable for other domains)
    firms_time_buffer_hours: Optional[float] = None
    firms_spatial_buffer_m: Optional[float] = None
    matching_firms_detection_count: Optional[int] = None
    nearest_firms_distance_m: Optional[float] = None

    is_demo: bool = True
    data_origin: DataOrigin = DataOrigin.SYNTHETIC_UI_FIXTURE
    disclaimer: str = "Synthetic development fixture — not an Earth observation result."
