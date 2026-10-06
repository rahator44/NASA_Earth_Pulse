"""
Exposure model (kept strictly separate from scientific observation state).
"""
from typing import Optional
from pydantic import BaseModel
from app.models.enums import DataOrigin


class ExposureResult(BaseModel):
    id: str
    analysis_id: str
    estimated_population: Optional[int] = None
    population_is_estimate: bool = True
    population_source: Optional[str] = None
    population_year: Optional[int] = None
    road_length_km: Optional[float] = None
    rail_length_km: Optional[float] = None
    bridge_count: Optional[int] = None
    hospital_count: Optional[int] = None
    settlement_count: Optional[int] = None
    notes: Optional[str] = None
    is_demo: bool = True
    data_origin: DataOrigin = DataOrigin.SYNTHETIC_UI_FIXTURE
    disclaimer: str = "Synthetic development fixture — not an Earth observation result."
