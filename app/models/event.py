"""
Event model representing items in the surface change feed and catalog.
"""
from typing import Optional
from pydantic import BaseModel
from app.models.enums import DataOrigin, Domain, ObservationState, ProductMaturity, ValidationStatus


class Event(BaseModel):
    id: str
    analysis_id: str
    title: str
    short_description: str
    domain: Domain
    observation_state: ObservationState
    aoi_id: str
    thumbnail_url: Optional[str] = None
    comparison_start: Optional[str] = None
    comparison_end: Optional[str] = None
    primary_measurement_label: Optional[str] = None
    primary_measurement_value: Optional[str] = None
    product_maturity: ProductMaturity = ProductMaturity.PROVISIONAL
    freshness_timestamp: Optional[str] = None
    validation_status: ValidationStatus = ValidationStatus.BETA_DEMO
    manifest_id: str
    featured: bool = False
    is_demo: bool = True
    data_origin: DataOrigin = DataOrigin.SYNTHETIC_UI_FIXTURE
    disclaimer: str = "Synthetic development fixture — not an Earth observation result."
