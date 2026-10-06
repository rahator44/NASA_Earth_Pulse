"""
Lab metrics models for the Scientist Image Lab.
Provides typed precomputed histograms, threshold previews, channel metadata,
and quality evaluations for exploratory evidence inspection.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field
from app.models.enums import DataOrigin


class HistogramData(BaseModel):
    label: str
    unit: Optional[str] = None
    bins: list[float] = Field(default_factory=list)
    counts: list[int] = Field(default_factory=list)
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    disclaimer: str = "Synthetic distribution — demonstration only."


class ThresholdPreviewState(BaseModel):
    threshold_value: float
    mask_url: str
    label: str


class ThresholdPreview(BaseModel):
    parameter_name: str
    unit: Optional[str] = None
    minimum: float
    maximum: float
    default: float
    step: float
    direction: str = "below_threshold"  # 'below_threshold', 'above_threshold', 'absolute_magnitude'
    preview_states: list[ThresholdPreviewState] = Field(default_factory=list)
    disclaimer: str = "Preview uses precomputed synthetic mask states."


class AnalysisLabMetrics(BaseModel):
    analysis_id: str
    data_origin: DataOrigin = DataOrigin.SYNTHETIC_UI_FIXTURE
    is_synthetic: bool = True
    disclaimer: str = (
        "Synthetic evidence and analysis controls are used to demonstrate the "
        "scientist workflow. These are not NISAR measurements."
    )
    active_channel: str
    available_channels: list[str] = Field(default_factory=list)
    channel_label: Optional[str] = None
    has_alternative_channel_assets: bool = False
    histogram: Optional[HistogramData] = None
    threshold_preview: Optional[ThresholdPreview] = None
    quality_summary: dict[str, Any] = Field(default_factory=dict)
    has_quality_mask: bool = False
    quality_mask_url: Optional[str] = None
    pixel_value_summary: Optional[str] = None
    notes: Optional[str] = None
