"""Human situation explanations for stored, processed analysis records."""
from fastapi import APIRouter, HTTPException

from app.models.situation import SituationRecord
from app.services.demo_data import demo_service


router = APIRouter(prefix="/api/analyses", tags=["situations"])


@router.get("/{analysis_id}/situation", response_model=SituationRecord)
async def get_analysis_situation(analysis_id: str) -> SituationRecord:
    situation = demo_service.get_situation_for_analysis(analysis_id)
    if situation is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return situation
