"""
Visual evidence asset models for Before/After radar comparison, difference maps, and change masks.
"""
from typing import Optional
from pydantic import BaseModel
from app.models.enums import DataOrigin


class EvidenceLayer(BaseModel):
    url: str
    label: str
    acquisition_id: Optional[str] = None
    acquisition_date: Optional[str] = None
    source: str = "Synthetic visual fixture"
    product: Optional[str] = None
    maturity: Optional[str] = None
    polarization: Optional[str] = None
    is_synthetic: bool = True


class EvidenceDifferenceLayer(BaseModel):
    url: str
    label: str = "Radar Backscatter Difference"
    unit: Optional[str] = "dB"
    legend_min: str = "-6.0 dB"
    legend_max: str = "+3.0 dB"
    colormap_label: str = "Cool-Warm Divergent"
    is_synthetic: bool = True


class EvidenceMaskLayer(BaseModel):
    url: str
    label: str = "Detected Change Mask"
    threshold_label: str = "Adaptive Otsu Threshold"
    is_synthetic: bool = True


class EvidenceContextLayer(BaseModel):
    url: str
    source: str = "Optical Reference Mock"
    date: Optional[str] = None
    is_synthetic: bool = True


class AnalysisEvidence(BaseModel):
    analysis_id: str
    before: Optional[EvidenceLayer] = None
    after: Optional[EvidenceLayer] = None
    difference: Optional[EvidenceDifferenceLayer] = None
    change_mask: Optional[EvidenceMaskLayer] = None
    optical_context: Optional[EvidenceContextLayer] = None
    change_regions_geojson_url: Optional[str] = None
    data_origin: DataOrigin = DataOrigin.SYNTHETIC_UI_FIXTURE
    disclaimer: str = (
        "Synthetic visual fixture — not NISAR imagery. "
        "Demonstrating evidence viewer mechanics only."
    )
    quality_gate_passed: bool = True
    quality_notes: Optional[str] = None
