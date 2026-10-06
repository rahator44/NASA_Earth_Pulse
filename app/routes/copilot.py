from typing import Optional
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.templates_config import templates
from app.services.demo_data import demo_service
from app.viewmodels.event_detail import build_event_detail_view

router = APIRouter()

@router.get("/copilot", response_class=HTMLResponse)
async def get_copilot(request: Request, event: Optional[str] = None):
    """Render deterministic responses grounded in a stored event view model."""
    event_view = build_event_detail_view(event, demo_service) if event else None
    context = None
    if event_view:
        before = event_view.before_acquisition
        after = event_view.after_acquisition
        context = {
            "event_id": event_view.id,
            "title": event_view.title,
            "aoi": f"{event_view.aoi_name}, {event_view.aoi_region}, {event_view.aoi_country}",
            "observation_state": event_view.observation_state_label,
            "observation_state_badge_class": event_view.observation_state_badge_class,
            "interpretation": event_view.resolved_explanation or event_view.domain_label,
            "analysis_id": event_view.analysis_id,
            "manifest_id": event_view.manifest_id,
            "before_date": before.formatted_date if before else "Unavailable",
            "after_date": after.formatted_date if after else "Unavailable",
            "before_id": before.id if before else "Unavailable",
            "after_id": after.id if after else "Unavailable",
            "product": event_view.situation.technical_metadata.product_name_public or "Unavailable",
            "validation": event_view.validation_statement,
            "validation_status": event_view.validation_status,
            "limitations": event_view.limitations or ["No additional limitations are recorded."],
            "measurement": "; ".join(
                f"{item.label}: {item.value}" for item in event_view.measurements
            ) or event_view.measurements_notice or "No measurement is recorded.",
            "evidence_url": event_view.image_lab_url,
            "is_synthetic": event_view.is_synthetic,
            "situation": event_view.situation.model_dump(mode="json"),
        }
    available_events = demo_service.get_events()
    return templates.TemplateResponse(
        request=request,
        name="pages/copilot.html",
        context={
            "active_page": "copilot",
            "event_id": event,
            "event_context": context,
            "requested_event_not_found": bool(event and not event_view),
            "available_events": available_events,
        },
    )
