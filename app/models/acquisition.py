"""
NISAR and auxiliary acquisition model.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field
from app.models.enums import DataOrigin, ProductMaturity, ProductType


class Acquisition(BaseModel):
    id: str
    source: str
    sensor: str
    product_type: ProductType
    acquisition_datetime: str
    track: int
    frame: int
    orbit_direction: str
    mode: str
    polarizations: list[str] = Field(default_factory=list)
    frequency: str
    bandwidth: str
    maturity: ProductMaturity = ProductMaturity.PROVISIONAL
    crid: str
    footprint: dict[str, Any]
    source_url: Optional[str] = None
    is_demo: bool = True
    data_origin: DataOrigin = DataOrigin.SYNTHETIC_UI_FIXTURE
    disclaimer: str = "Synthetic development fixture — not an Earth observation result."
