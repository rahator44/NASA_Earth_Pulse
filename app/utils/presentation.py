"""
Presentation helpers and view models for NISAR Surface Change Explorer.
Converts domain enums and raw data into scientifically safe, human-readable UI formats.
"""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel

from app.models import Domain, Event, ObservationState, ProductMaturity, ValidationStatus, DataOrigin

DOMAIN_DISPLAY_NAMES = {
    Domain.WILDFIRE: "Vegetation Disturbance",
    Domain.FLOOD_WETLAND: "Flood / Wetland",
    Domain.GLACIER: "Glacier Change",
    Domain.DEFORMATION: "Ground Deformation",
    Domain.UNCLASSIFIED: "Unclassified Change",
}

DOMAIN_FALLBACK_ICONS = {
    Domain.WILDFIRE: "flame",
    Domain.FLOOD_WETLAND: "waves",
    Domain.GLACIER: "mountain-snow",
    Domain.DEFORMATION: "activity",
    Domain.UNCLASSIFIED: "radar",
}

DOMAIN_FALLBACK_TAGS = {
    Domain.WILDFIRE: "CANOPY BACKSCATTER ANOMALY",
    Domain.FLOOD_WETLAND: "DUAL-POL HYDROLOGY MAPPING",
    Domain.GLACIER: "ICE VELOCITY SPECKLE TRACKING",
    Domain.DEFORMATION: "INSAR INTERFEROGRAM FRINGES",
    Domain.UNCLASSIFIED: "RADAR SIGNAL ANOMALY",
}

OBSERVATION_STATE_DISPLAY = {
    ObservationState.NO_CHANGE: ("NO CHANGE", "badge-state-no-change"),
    ObservationState.CHANGE_DETECTED: ("CHANGE DETECTED", "badge-state-change"),
    ObservationState.STRONG_CHANGE: ("STRONG CHANGE", "badge-state-strong"),
    ObservationState.UNKNOWN_CHANGE: ("UNKNOWN CHANGE", "badge-state-unknown"),
    ObservationState.INSUFFICIENT_DATA: ("INSUFFICIENT DATA", "badge-state-insufficient"),
}

VALIDATION_STATUS_DISPLAY = {
    ValidationStatus.VALIDATED: ("Validated", "badge-validated"),
    ValidationStatus.CALIBRATED_ONLY: ("Calibrated only", "badge-validation"),
    ValidationStatus.BETA_DEMO: ("BETA demo", "badge-maturity"),
    ValidationStatus.UNVALIDATED: ("Unvalidated", "badge-maturity"),
}


def format_domain_label(domain: Domain | str) -> str:
    """Returns presentation-safe domain name (e.g. wildfire -> 'Vegetation Disturbance')."""
    if isinstance(domain, str):
        try:
            domain = Domain(domain)
        except ValueError:
            return "Unclassified Change"
    return DOMAIN_DISPLAY_NAMES.get(domain, "Unclassified Change")


def format_observation_state(state: ObservationState | str) -> tuple[str, str]:
    """Returns (human_readable_label, badge_css_class)."""
    if isinstance(state, str):
        try:
            state = ObservationState(state)
        except ValueError:
            return ("UNKNOWN STATE", "badge-state-insufficient")
    return OBSERVATION_STATE_DISPLAY.get(state, ("UNKNOWN STATE", "badge-state-insufficient"))


def format_validation_status(status: ValidationStatus | str) -> tuple[str, str]:
    """Returns (human_readable_label, badge_css_class)."""
    if isinstance(status, str):
        try:
            status = ValidationStatus(status)
        except ValueError:
            return ("Unvalidated", "badge-maturity")
    return VALIDATION_STATUS_DISPLAY.get(status, ("Unvalidated", "badge-maturity"))


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        clean_str = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        return None


def format_date_range(start_str: Optional[str], end_str: Optional[str]) -> str:
    """Formats comparison dates: '01 AUG → 13 AUG 2026'."""
    start_dt = parse_date(start_str)
    end_dt = parse_date(end_str)

    if start_dt and end_dt:
        if start_dt.year == end_dt.year:
            return f"{start_dt.strftime('%d %b').upper()} → {end_dt.strftime('%d %b %Y').upper()}"
        return f"{start_dt.strftime('%d %b %Y').upper()} → {end_dt.strftime('%d %b %Y').upper()}"
    elif start_dt:
        return f"{start_dt.strftime('%d %b %Y').upper()}"
    elif end_dt:
        return f"{end_dt.strftime('%d %b %Y').upper()}"
    return "Comparison dates unavailable"


class EventCardView(BaseModel):
    """Presentation view model for rendering Event records in the UI."""
    id: str
    analysis_id: str
    title: str
    short_description: str
    domain_raw: str
    domain_label: str
    observation_state_raw: str
    observation_state_label: str
    observation_state_badge_class: str
    is_synthetic: bool
    disclaimer: str
    date_range_display: str
    primary_measurement_label: Optional[str] = None
    primary_measurement_value: Optional[str] = None
    product_maturity_label: str
    product_maturity_badge_class: str
    validation_status_label: str
    validation_status_badge_class: str
    thumbnail_url: Optional[str] = None
    fallback_icon: str
    fallback_graphic_tag: str
    featured: bool
    detail_url: str
    source: str = "NASA NISAR / ASF DAAC"


def format_event_card(event: Event) -> EventCardView:
    domain_label = format_domain_label(event.domain)
    state_label, state_badge_class = format_observation_state(event.observation_state)
    val_label, val_badge_class = format_validation_status(event.validation_status)
    date_display = format_date_range(event.comparison_start, event.comparison_end)

    # State-specific public descriptions
    short_desc = event.short_description
    if event.observation_state == ObservationState.UNKNOWN_CHANGE:
        if not short_desc or "unusual" not in short_desc.lower():
            short_desc = "Unusual radar change detected. Cause not identified."
    elif event.observation_state == ObservationState.INSUFFICIENT_DATA:
        short_desc = "Not enough usable data to determine surface change."
    elif event.observation_state == ObservationState.NO_CHANGE:
        short_desc = "No significant surface change was detected in the analyzed observations."

    # Maturity styling
    maturity_val = event.product_maturity.value if hasattr(event.product_maturity, "value") else str(event.product_maturity)
    maturity_badge_class = "badge-maturity"
    if maturity_val == "BETA":
        maturity_badge_class = "badge-maturity border-[#1E6BFF]/40 text-[#60A5FA]"

    # Synthetic determination (automatically false for precomputed_real_analysis)
    is_synthetic = (
        event.data_origin == DataOrigin.SYNTHETIC_UI_FIXTURE or 
        getattr(event, "is_demo", False)
    )
    if not is_synthetic and event.comparison_start and "2026-06-28" in str(event.comparison_start):
        date_display = "2026-06-28 → 2026-07-10" 

    domain_enum = event.domain if isinstance(event.domain, Domain) else Domain(event.domain)

    # Primary measurement handling (only if both label and value exist and not insufficient data)
    meas_label = event.primary_measurement_label
    meas_val = event.primary_measurement_value
    if event.observation_state == ObservationState.INSUFFICIENT_DATA:
        # Do not show change measurement for insufficient data
        if meas_label and ("inundated" in meas_label.lower() or "area" in meas_label.lower()):
            meas_label = None
            meas_val = None

    return EventCardView(
        id=event.id,
        analysis_id=event.analysis_id,
        title=event.title,
        short_description=short_desc,
        domain_raw=event.domain.value if hasattr(event.domain, "value") else str(event.domain),
        domain_label=domain_label,
        observation_state_raw=event.observation_state.value if hasattr(event.observation_state, "value") else str(event.observation_state),
        observation_state_label=state_label,
        observation_state_badge_class=state_badge_class,
        is_synthetic=is_synthetic,
        disclaimer=event.disclaimer,
        date_range_display=date_display,
        primary_measurement_label=meas_label,
        primary_measurement_value=meas_val,
        product_maturity_label=maturity_val,
        product_maturity_badge_class=maturity_badge_class,
        validation_status_label=val_label,
        validation_status_badge_class=val_badge_class,
        thumbnail_url=event.thumbnail_url,
        fallback_icon=DOMAIN_FALLBACK_ICONS.get(domain_enum, "radar"),
        fallback_graphic_tag=DOMAIN_FALLBACK_TAGS.get(domain_enum, "RADAR ANOMALY"),
        featured=event.featured,
        detail_url=f"/event/{event.id}",
        source="NASA NISAR / ASF DAAC",
    )


def get_event_card_views(events: list[Event]) -> list[EventCardView]:
    return [format_event_card(ev) for ev in events]
