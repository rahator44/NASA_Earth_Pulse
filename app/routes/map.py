from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.templates_config import templates
from app.config import get_mapbox_public_token

router = APIRouter()

@router.get("/map", response_class=HTMLResponse)
async def get_map(request: Request):
    """Route 2: Map + Coverage Explorer"""
    return templates.TemplateResponse(
        request=request,
        name="pages/map.html",
        context={"active_page": "map", "mapbox_public_token": get_mapbox_public_token()},
    )
