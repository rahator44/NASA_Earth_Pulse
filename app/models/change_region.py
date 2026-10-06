"""
Change Region model for spatial detected polygons.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field
from app.models.enums import ClassificationStatus, DataOrigin


class ChangeRegion(BaseModel):
    id: str
    analysis_id: str
    geometry: dict[str, Any]
    area_km2: Optional[float] = None
    classification_status: ClassificationStatus
    final_classification: Optional[str] = None
    context_tags: list[str] = Field(default_factory=list)
    is_demo: bool = True
    data_origin: DataOrigin = DataOrigin.SYNTHETIC_UI_FIXTURE
    disclaimer: str = "Synthetic development fixture — not an Earth observation result."
