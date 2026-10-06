from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates_config import templates

router = APIRouter()

@router.get("/setting", response_class=RedirectResponse)
async def redirect_to_settings():
    """Redirect /setting singular to /settings."""
    return RedirectResponse(url="/settings", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@router.get("/settings", response_class=HTMLResponse)
async def get_settings(request: Request):
    """Route 8: Settings / Language"""
    return templates.TemplateResponse(
        request=request,
        name="pages/settings.html",
        context={"active_page": "settings"},
    )
