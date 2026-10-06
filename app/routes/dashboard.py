from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.templates_config import templates
from app.services.demo_data import demo_service
from app.viewmodels.dashboard import build_dashboard_view
from app.config import get_mapbox_public_token

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """
    Route 6: Situation Dashboard
    Regional review workspace displaying analyzed areas,
    separating actual detected changes from No Change and Insufficient Data areas,
    and calculating dataset-relative Review Priority triage scores.
    """
    dashboard_view = build_dashboard_view(demo_service)

    return templates.TemplateResponse(
        request=request,
        name="pages/dashboard.html",
        context={
            "active_page": "dashboard",
            "dashboard": dashboard_view,
            "mapbox_public_token": get_mapbox_public_token(),
        },
    )
