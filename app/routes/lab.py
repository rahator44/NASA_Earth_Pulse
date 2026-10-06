from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates_config import templates
from app.services.demo_data import demo_service
from app.viewmodels.lab import build_lab_detail_view

router = APIRouter()

@router.get("/lab", response_class=HTMLResponse)
async def get_lab_index():
    """Redirect /lab root to the primary real NISAR showcase analysis."""
    return RedirectResponse(url="/lab/real_flood_001", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@router.get("/lab/{analysis_id}", response_class=HTMLResponse)
async def get_lab_analysis(request: Request, analysis_id: str):
    """
    Route 5: Scientist Image Lab
    Renders visual evidence viewer and exploratory analysis controls.
    Returns HTTP 404 with styled page if analysis does not exist.
    """
    lab_view = build_lab_detail_view(analysis_id, demo_service)
    
    if not lab_view:
        return templates.TemplateResponse(
            request=request,
            name="pages/404.html",
            context={
                "active_page": "lab",
                "analysis_id": analysis_id,
                "is_lab_404": True,
            },
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return templates.TemplateResponse(
        request=request,
        name="pages/lab.html",
        context={
            "active_page": "lab",
            "analysis_id": analysis_id,
            "lab": lab_view,
            "evidence": lab_view.evidence,
        },
    )
