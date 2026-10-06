"""
Area of Interest (AOI) model.
"""
from typing import Any, Optional
from pydantic import BaseModel
from app.models.enums import DataOrigin


class AOI(BaseModel):
    id: str
    display_name: str
    geometry: dict[str, Any]
    country: Optional[str] = None
    region: Optional[str] = None
    is_demo: bool = True
    data_origin: DataOrigin = DataOrigin.SYNTHETIC_UI_FIXTURE
    disclaimer: str = "Synthetic development fixture — not an Earth observation result."
