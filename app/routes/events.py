from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates_config import templates
from app.services.demo_data import demo_service
from app.viewmodels.event_detail import build_event_detail_view
from app.config import get_mapbox_public_token

router = APIRouter()

@router.get("/event", response_class=RedirectResponse)
@router.get("/events", response_class=RedirectResponse)
async def redirect_to_events_dashboard():
    """Redirect catalog requests without an event ID to the main Situation Dashboard."""
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@router.get("/event/{event_id}", response_class=HTMLResponse)
async def get_event_detail(request: Request, event_id: str):
    """
    Route 3: Event Detail
    Renders fully data-driven scientific observation page.
    Returns HTTP 404 with styled page if event does not exist.
    """
    event_view = build_event_detail_view(event_id, demo_service)
    
    if not event_view:
        return templates.TemplateResponse(
            request=request,
            name="pages/404.html",
            context={
                "active_page": "event",
                "event_id": event_id,
            },
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return templates.TemplateResponse(
        request=request,
        name="pages/event_detail.html",
        context={
            "active_page": "event",
            "event": event_view,
            "event_id": event_id,
            "mapbox_public_token": get_mapbox_public_token(),
        },
    )
