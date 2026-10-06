from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.templates_config import templates

router = APIRouter()

@router.get("/methods", response_class=HTMLResponse)
async def get_methods(request: Request):
    """Route 7: Methods + Validation"""
    return templates.TemplateResponse(
        request=request,
        name="pages/methods.html",
        context={"active_page": "methods"},
    )
