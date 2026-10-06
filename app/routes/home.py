"""
Home Route: Editorial Earth-Observation Change Feed.
Retrieves validated Event records from DemoDataService and renders via Jinja2.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.templates_config import templates
from app.services.demo_data import demo_service
from app.utils.presentation import get_event_card_views

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    """
    Route 1: Home / Change Feed
    """
    all_events = demo_service.get_events()
    event_views = get_event_card_views(all_events)
    real_events = [ev for ev in event_views if not ev.is_synthetic]
    demo_events = [ev for ev in event_views if ev.is_synthetic]

    return templates.TemplateResponse(
        request=request,
        name="pages/home.html",
        context={
            "active_page": "home",
            "events": event_views,
            "real_events": real_events,
            "demo_events": demo_events,
            "total_count": len(event_views),
        },
    )
