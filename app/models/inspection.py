"""
Pydantic models for Map Area Inspection requests and structured responses.
"""
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field
from app.models.situation import SituationRecord

SelectionType = Literal["point", "rectangle", "polygon"]


class AreaInspectionRequest(BaseModel):
    """Payload sent by client when clicking or drawing on the map."""
    geometry: Optional[dict[str, Any]] = Field(default=None, description="GeoJSON geometry object (Point or Polygon)")
    selection_type: SelectionType = Field("point", description="Type of selection: point, rectangle, or polygon")
    aoi_id: Optional[str] = Field(default=None, description="Direct AOI lookup identifier")


class InspectionCandidate(BaseModel):
    """Minimal representation of a candidate domain interpretation."""
    id: str
    candidate_domain: str
    candidate_domain_label: str
    candidate_score: Optional[float] = None
    supported: bool
    notes: Optional[str] = None
    has_physical_evidence: bool = True
    has_independent_evidence: bool = False
    is_demo: bool = True
    data_origin: str = "synthetic_ui_fixture"
    disclaimer: str = "Synthetic development fixture — not an Earth observation result."


class InspectionExposure(BaseModel):
    """Exposure context summary associated with an analyzed area."""
    estimated_population: Optional[int] = None
    population_is_estimate: bool = True
    road_length_km: Optional[float] = None
    settlement_count: Optional[int] = None
    is_demo: bool = True
    data_origin: str = "synthetic_ui_fixture"
    notes: Optional[str] = None
    disclaimer: str = "Synthetic development fixture — not an Earth observation result."


class InspectionMatch(BaseModel):
    """Enriched inspection match combining AOI, Analysis, Event, and Provenance."""
    aoi_id: str
    aoi_display_name: str
    aoi_country: Optional[str] = None
    aoi_region: Optional[str] = None
    
    analysis_id: str
    domain_raw: str
    domain_label: str
    observation_state_raw: str
    observation_state_label: str
    observation_state_badge_class: str
    
    event_id: Optional[str] = None
    event_title: Optional[str] = None
    event_description: Optional[str] = None
    comparison_start: Optional[str] = None
    comparison_end: Optional[str] = None
    date_range_display: str
    
    primary_measurement_label: Optional[str] = None
    primary_measurement_value: Optional[str] = None
    
    product_maturity_label: str
    validation_status_label: str
    validation_status_badge_class: str
    quality_notes: Optional[str] = None
    quality_gate_passed: bool = True
    
    manifest_id: Optional[str] = None
    
    candidates: list[InspectionCandidate] = Field(default_factory=list)
    exposure: Optional[InspectionExposure] = None
    
    is_demo: bool = True
    data_origin: str = "synthetic_ui_fixture"
    disclaimer: str = "Synthetic development fixture — not an Earth observation result."
    situation: Optional[SituationRecord] = None


class AreaInspectionResponse(BaseModel):
    """Structured response returned by POST /api/demo/inspect-area."""
    selection_type: str
    coordinates_display: Optional[str] = None
    has_processed_analysis: bool
    matched_count: int = 0
    matched_aoi_ids: list[str] = Field(default_factory=list)
    matched_aois: list[dict[str, Any]] = Field(default_factory=list)
    analyses: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    change_regions: list[dict[str, Any]] = Field(default_factory=list)
    matches: list[InspectionMatch] = Field(default_factory=list)
    is_demo: bool = True
    data_origin: str = "synthetic_ui_fixture"
    disclaimer: str = "Synthetic development fixtures — not an Earth observation result."
    notice: Optional[str] = None
