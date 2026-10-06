"""Human-readable, evidence-linked interpretation records."""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


SupportLevel = Literal[
    "direct_measurement", "independent_support", "contextual", "contradicting"
]
InterpretationStatus = Literal["supported", "possible", "ambiguous", "not_supported"]


class DecodedNISARMetadata(BaseModel):
    product_code: Optional[str] = None
    product_name_technical: Optional[str] = None
    product_name_public: Optional[str] = None
    product_explanation: Optional[str] = None
    processing_level: Optional[str] = None
    processing_type_code: Optional[str] = None
    processing_type_label: Optional[str] = None
    cycle: Optional[int] = None
    bandwidth_mode_code: Optional[str] = None
    bandwidth_mode_explanation: Optional[str] = None
    polarization_mode_code: Optional[str] = None
    polarization_mode_explanation: Optional[str] = None
    source_code: Optional[str] = None
    source_explanation: Optional[str] = None
    orbit_accuracy_code: Optional[str] = None
    orbit_accuracy_explanation: Optional[str] = None
    coverage_code: Optional[str] = None
    coverage_explanation: Optional[str] = None
    processing_location_code: Optional[str] = None
    processing_location_explanation: Optional[str] = None
    product_counter: Optional[str] = None
    maturity_code: Optional[str] = None
    maturity_label: Optional[str] = None
    maturity_explanation: Optional[str] = None
    orbit_direction: Optional[str] = None
    orbit_direction_public: Optional[str] = None
    track: Optional[int] = None
    track_explanation: Optional[str] = None
    frame: Optional[int] = None
    frame_explanation: Optional[str] = None
    mode: Optional[str] = None
    frequency: Optional[str] = None
    bandwidth: Optional[str] = None
    polarizations: list[str] = Field(default_factory=list)
    polarization_explanations: list[str] = Field(default_factory=list)
    acquisition_dates: list[str] = Field(default_factory=list)
    processing_version: Optional[str] = None
    processing_version_explanation: Optional[str] = None
    analysis_pipeline_version: Optional[str] = None
    code_version: Optional[str] = None
    crid: Optional[str] = None
    crid_explanation: Optional[str] = None
    comparison_policy: Optional[str] = None
    dataset_path: Optional[str] = None
    quality_parameters: dict[str, Any] = Field(default_factory=dict)
    detection_parameters: dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
    before_granule_id: Optional[str] = None
    after_granule_id: Optional[str] = None


class SituationEvidence(BaseModel):
    evidence_type: str
    measurement_name: str
    measurement_value: Optional[Any] = None
    measurement_unit: Optional[str] = None
    direction: Optional[str] = None
    quality_status: Optional[str] = None
    quality_value: Optional[Any] = None
    description_public: str
    description_scientist: Optional[str] = None
    source: Optional[str] = None
    support_level: SupportLevel


class SituationInterpretation(BaseModel):
    code: str
    public_label: str
    scientific_label: str
    description: str
    status: InterpretationStatus
    reason: str
    # Explainability metadata. These IDs are application rule identifiers, not NASA hazard codes.
    rule_id: Optional[str] = None
    public_reason: Optional[str] = None
    evidence_ids: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class SituationRecord(BaseModel):
    analysis_id: Optional[str] = None
    event_id: Optional[str] = None
    aoi_id: Optional[str] = None
    observation_state: str
    headline: str
    summary: str
    what_changed: str
    what_nisar_measured: str
    interpretations: list[SituationInterpretation] = Field(default_factory=list)
    direct_evidence: list[SituationEvidence] = Field(default_factory=list)
    supporting_evidence: list[SituationEvidence] = Field(default_factory=list)
    contradicting_evidence: list[SituationEvidence] = Field(default_factory=list)
    context: list[SituationEvidence] = Field(default_factory=list)
    data_quality: dict[str, Any] = Field(default_factory=dict)
    what_we_cannot_say: list[str] = Field(default_factory=list)
    recommended_public_wording: str
    technical_metadata: Optional[DecodedNISARMetadata] = None
    manifest_id: Optional[str] = None
    data_origin: str
    human_label: str
