"""
Situation Dashboard Presentation View Model.
Organizes analyzed areas, calculates dataset-relative Review Priority,
and separates actual detected changes from No Change and Insufficient Data areas.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.models.enums import ObservationState
from app.models.review_priority import ReviewPriorityResult
from app.services.demo_data import DemoDataService
from app.services.review_priority import (
    calculate_review_priority_for_analysis,
    compute_dataset_exposure_scores,
    normalize_observation_state_key,
)
from app.utils.presentation import (
    format_date_range,
    format_domain_label,
    format_observation_state,
    format_validation_status,
)


class DashboardSummaryCards(BaseModel):
    """Aggregate observation counts for the dashboard header."""
    change_detected_count: int = 0
    strong_change_count: int = 0
    unknown_change_count: int = 0
    no_change_count: int = 0
    insufficient_data_count: int = 0
    total_analyzed_count: int = 0


class ReviewQueueItem(BaseModel):
    """Reviewable change record scored with Review Priority."""
    analysis_id: str
    event_id: Optional[str] = None
    event_url: Optional[str] = None
    map_url: str
    lab_url: str

    aoi_id: str
    aoi_name: str
    aoi_country: str
    aoi_region: str

    domain_raw: str
    domain_label: str

    observation_state_raw: str
    observation_state_label: str
    observation_state_badge_class: str

    interpretation_title: str
    interpretation_summary: str
    candidate_interpretations: list[str] = Field(default_factory=list)

    comparison_range_display: str
    comparison_start_display: str
    comparison_end_display: str

    primary_measurement_label: Optional[str] = None
    primary_measurement_value: Optional[str] = None

    estimated_population: Optional[int] = None
    estimated_population_display: str = "Unavailable"
    infrastructure_summary: str = ""

    validation_status: str
    validation_label: str
    validation_badge_class: str
    validation_statement: str

    # Review Priority Details
    priority: ReviewPriorityResult
    priority_badge_class: str


class NoChangeItem(BaseModel):
    """Baseline area with confirmed geodetic or surface stability (Unscored)."""
    analysis_id: str
    event_id: Optional[str] = None
    event_url: Optional[str] = None
    map_url: str
    lab_url: str

    aoi_id: str
    aoi_name: str
    aoi_country: str
    aoi_region: str

    domain_label: str
    comparison_range_display: str
    quality_gate_passed: bool = True
    quality_notes: str = ""
    primary_measurement_label: Optional[str] = None
    primary_measurement_value: Optional[str] = None
    validation_statement: str = ""


class InsufficientDataItem(BaseModel):
    """Incomplete area with failed quality gates or missing observations (Unscored)."""
    analysis_id: str
    event_id: Optional[str] = None
    event_url: Optional[str] = None
    map_url: str
    lab_url: str

    aoi_id: str
    aoi_name: str
    aoi_country: str
    aoi_region: str

    domain_label: str
    comparison_range_display: str
    valid_pixel_fraction_display: str = "0.0%"
    quality_failure_reason: str = ""
    available_context: str = ""


class DashboardDetailView(BaseModel):
    """Complete presentation model for the Situation Dashboard."""
    summary: DashboardSummaryCards
    surface_changes: list[dict[str, Any]] = Field(default_factory=list)
    review_queue: list[ReviewQueueItem] = Field(default_factory=list)
    review_queue_json: list[dict[str, Any]] = Field(default_factory=list)
    no_change_areas: list[NoChangeItem] = Field(default_factory=list)
    insufficient_areas: list[InsufficientDataItem] = Field(default_factory=list)

    # Map GeoJSON
    map_geojson: dict[str, Any] = Field(default_factory=dict)

    # Disclaimers & Method Constants
    is_synthetic: bool = True
    synthetic_badge_text: str = "DEMO DASHBOARD"
    synthetic_warning: str = "Synthetic development fixtures — not Earth observation results. This dashboard also includes one clearly labeled real precomputed NISAR showcase."
    triage_disclaimer: str = (
        "Review Priority is a demonstration interface aid, not an emergency measure. "
        "It does not describe physical magnitude or hazard severity."
    )
    dense_city_explanation: str = (
        "Exposure data unavailable. Population and infrastructure estimates are not used or displayed."
    )
    dataset_relative_note: str = (
        "This dashboard contains synthetic interface fixtures; exposure values are unavailable."
    )


def _get_priority_badge_class(band: str) -> str:
    """Return neutral, non-alarm styling classes for Review Priority."""
    if band == "HIGH":
        return "border-[#4338CA] bg-[#1E1B4B]/80 text-[#818CF8]"
    if band == "MEDIUM":
        return "border-[#0284C7] bg-[#0C2B4E]/80 text-[#38BDF8]"
    return "border-[#334155] bg-[#1E293B]/80 text-[#94A3B8]"


def _get_observation_state_color(state_key: str) -> str:
    """Return scientific map color tied strictly to Observation State (non-alarm palette)."""
    mapping = {
        "no_change": "#4E7880",         # Muted teal / cool gray
        "change_detected": "#1E6BFF",   # Royal blue
        "strong_change": "#00D2FF",     # Cyan / bright blue
        "unknown_change": "#8B5CF6",    # Violet / purple
        "insufficient_data": "#64748B", # Slate gray
    }
    return mapping.get(state_key, "#64748B")


def build_dashboard_view(demo_service: DemoDataService) -> DashboardDetailView:
    """
    Constructs the Situation Dashboard presentation model from active demo data.
    Separates actual changes from No Change and Insufficient Data areas.
    """
    # Show every stored analysis in the scientific overview/map.  Keep the
    # real showcase out of Review Priority until authoritative exposure data
    # exists so the dashboard never fabricates population/infrastructure risk.
    analyses = list(demo_service.get_analyses())
    triage_analyses = [a for a in analyses if a.id != "real_flood_001"]
    events = demo_service.get_events()
    aois = {a.id: a for a in demo_service.get_aois()}
    # Exposure fixtures are not authoritative WorldPop/OSM context, so the
    # dashboard must treat exposure as unavailable instead of using them.
    exposures = {}
    validations = demo_service.validation_results

    # Map events by analysis_id
    events_by_analysis = {ev.analysis_id: ev for ev in events}

    # Summary counts
    summary = DashboardSummaryCards(total_analyzed_count=len(analyses))
    for a in analyses:
        s_key = normalize_observation_state_key(a.observation_state)
        if s_key == "change_detected":
            summary.change_detected_count += 1
        elif s_key == "strong_change":
            summary.strong_change_count += 1
        elif s_key == "unknown_change":
            summary.unknown_change_count += 1
        elif s_key == "no_change":
            summary.no_change_count += 1
        elif s_key == "insufficient_data":
            summary.insufficient_data_count += 1

    # Find reviewable analyses: change_detected, strong_change, unknown_change
    reviewable_analyses = [
        a for a in triage_analyses
        if normalize_observation_state_key(a.observation_state) in {
            "change_detected", "strong_change", "unknown_change"
        }
    ]

    # Find reference timestamp (latest observation among analyses)
    latest_ts = None
    for a in analyses:
        ev = events_by_analysis.get(a.id)
        candidate_ts = ev.freshness_timestamp if ev else a.created_at
        if candidate_ts:
            if latest_ts is None or str(candidate_ts) > str(latest_ts):
                latest_ts = str(candidate_ts)

    # Compute dataset-relative exposure scores for reviewable analyses
    reviewable_exposure_dicts: list[dict[str, Any]] = []
    for a in reviewable_analyses:
        exp = exposures.get(a.id)
        if exp:
            reviewable_exposure_dicts.append({
                "analysis_id": a.id,
                "estimated_population": exp.estimated_population,
                "road_length_km": exp.road_length_km,
                "rail_length_km": exp.rail_length_km,
                "bridge_count": exp.bridge_count,
                "hospital_count": exp.hospital_count,
                "settlement_count": exp.settlement_count,
            })
        else:
            reviewable_exposure_dicts.append({
                "analysis_id": a.id,
                "estimated_population": None,
            })

    dataset_exp_scores = compute_dataset_exposure_scores(reviewable_exposure_dicts)

    # Human-readable surface-change overview.  This includes the real showcase
    # even when it is intentionally excluded from Review Priority scoring.
    surface_changes: list[dict[str, Any]] = []
    for a in analyses:
        s_key = normalize_observation_state_key(a.observation_state)
        if s_key not in {"change_detected", "strong_change", "unknown_change"}:
            continue
        aoi = aois.get(a.aoi_id)
        ev = events_by_analysis.get(a.id)
        situation = demo_service.get_situation_for_analysis(a.id)
        primary = next((item for item in (situation.direct_evidence if situation else []) if item.measurement_value is not None), None)
        state_label, state_badge = format_observation_state(a.observation_state)
        interpretation = situation.interpretations[0].public_label if situation and situation.interpretations else "Unclassified surface change"
        surface_changes.append({
            "analysis_id": a.id,
            "event_id": ev.id if ev else None,
            "aoi_id": a.aoi_id,
            "aoi_name": aoi.display_name if aoi else a.aoi_id,
            "aoi_country": aoi.country if aoi else "Global",
            "observation_state_raw": s_key,
            "observation_state_label": state_label,
            "observation_state_badge_class": state_badge,
            "headline": situation.headline if situation else state_label,
            "interpretation": interpretation,
            "explanation": situation.what_changed if situation else "A stored analysis reports surface change.",
            "quality": situation.data_quality.get("status") if situation else "Not assessed",
            "primary_measurement": (
                f"{primary.measurement_name}: {primary.measurement_value} {primary.measurement_unit or ''}".strip()
                if primary else None
            ),
            "human_label": situation.human_label if situation else "ANALYSIS RECORD",
            "is_real": str(getattr(a.data_origin, "value", a.data_origin)) == "precomputed_real_analysis",
            "event_url": f"/event/{ev.id}" if ev else None,
            "map_url": f"/map?aoi={a.aoi_id}",
            "lab_url": f"/lab/{a.id}",
        })

    # Real analyses first, then strongest/unknown/change ordering.
    state_order = {"strong_change": 0, "change_detected": 1, "unknown_change": 2}
    surface_changes.sort(key=lambda item: (not item["is_real"], state_order.get(item["observation_state_raw"], 9), item["aoi_name"]))

    # Build Review Queue
    review_queue: list[ReviewQueueItem] = []
    for a in reviewable_analyses:
        aoi = aois.get(a.aoi_id)
        aoi_name = aoi.display_name if aoi else a.aoi_id
        aoi_country = aoi.country if aoi else "Global"
        aoi_region = aoi.region if aoi else ""

        ev = events_by_analysis.get(a.id)
        exp = exposures.get(a.id)
        situation = demo_service.get_situation_for_analysis(a.id)
        primary_situation_measurement = next(
            (item for item in (situation.direct_evidence if situation else []) if item.measurement_value is not None),
            None,
        )
        val = validations.get(a.id)

        s_key = normalize_observation_state_key(a.observation_state)
        s_label, s_badge = format_observation_state(a.observation_state)
        d_label = format_domain_label(a.domain)
        v_label, v_badge = format_validation_status(val.status if val else "unvalidated")

        obs_time = ev.freshness_timestamp if ev else a.created_at
        exp_metrics = dataset_exp_scores.get(a.id)

        # Calculate Review Priority
        priority_res = calculate_review_priority_for_analysis(
            analysis_id=a.id,
            observation_state=a.observation_state,
            exposure_dict=exp.model_dump() if exp else None,
            dataset_exposure_metrics=exp_metrics,
            observation_time=obs_time,
            dataset_latest_time=latest_ts,
            event_id=ev.id if ev else None,
        )

        if not priority_res:
            continue

        # Interpretation comes from the deterministic SituationRecord. Never hard-code causes here.
        if situation:
            interp_title = situation.headline
            interp_summary = situation.what_changed
            cand_list = [
                f"{item.public_label} — {item.status.replace('_', ' ')}"
                for item in situation.interpretations[1:]
            ]
        else:
            interp_title = ev.title if ev else f"{d_label} Detection"
            interp_summary = ev.short_description if ev else "A stored analysis reports surface change."
            cand_list = []

        # Population & Infrastructure display
        pop_display = f"{exp.estimated_population:,}" if (exp and exp.estimated_population is not None) else "Unavailable"
        
        infra_parts: list[str] = []
        if exp:
            if exp.road_length_km:
                infra_parts.append(f"{exp.road_length_km:.1f} km roads")
            if exp.bridge_count:
                infra_parts.append(f"{exp.bridge_count} bridges")
            if exp.hospital_count:
                infra_parts.append(f"{exp.hospital_count} hospitals")
            if exp.settlement_count:
                infra_parts.append(f"{exp.settlement_count} settlements")
        infra_summary = ", ".join(infra_parts) if infra_parts else "Exposure data unavailable"

        if val and val.independent_validation:
            val_statement = f"Independently validated on {val.number_of_independent_events} event(s)"
        elif val:
            val_statement = "Calibration/context only — not independently validated"
        else:
            val_statement = "No validation record available"

        review_queue.append(ReviewQueueItem(
            analysis_id=a.id,
            event_id=ev.id if ev else None,
            event_url=f"/event/{ev.id}" if ev else None,
            map_url=f"/map?aoi={a.aoi_id}",
            lab_url=f"/lab/{a.id}",
            aoi_id=a.aoi_id,
            aoi_name=aoi_name,
            aoi_country=aoi_country,
            aoi_region=aoi_region,
            domain_raw=a.domain.value,
            domain_label=d_label,
            observation_state_raw=s_key,
            observation_state_label=s_label,
            observation_state_badge_class=s_badge,
            interpretation_title=interp_title,
            interpretation_summary=interp_summary,
            candidate_interpretations=cand_list,
            comparison_range_display=format_date_range(ev.comparison_start if ev else None, ev.comparison_end if ev else None),
            comparison_start_display=str(ev.comparison_start)[:10] if (ev and ev.comparison_start) else "N/A",
            comparison_end_display=str(ev.comparison_end)[:10] if (ev and ev.comparison_end) else "N/A",
            primary_measurement_label=ev.primary_measurement_label if ev else None,
            primary_measurement_value=ev.primary_measurement_value if ev else None,
            estimated_population=exp.estimated_population if exp else None,
            estimated_population_display=pop_display,
            infrastructure_summary=infra_summary,
            validation_status=val.status.value if val else "unvalidated",
            validation_label=v_label,
            validation_badge_class=v_badge,
            validation_statement=val_statement,
            priority=priority_res,
            priority_badge_class=_get_priority_badge_class(priority_res.priority_band),
        ))

    # Sort review_queue by review_score descending by default
    review_queue.sort(key=lambda item: item.priority.review_score, reverse=True)

    # Build No Change Section
    no_change_areas: list[NoChangeItem] = []
    for a in analyses:
        s_key = normalize_observation_state_key(a.observation_state)
        if s_key != "no_change":
            continue

        aoi = aois.get(a.aoi_id)
        ev = events_by_analysis.get(a.id)
        val = validations.get(a.id)

        no_change_areas.append(NoChangeItem(
            analysis_id=a.id,
            event_id=ev.id if ev else None,
            event_url=f"/event/{ev.id}" if ev else None,
            map_url=f"/map?aoi={a.aoi_id}",
            lab_url=f"/lab/{a.id}",
            aoi_id=a.aoi_id,
            aoi_name=aooi_name if (aooi_name := (aoi.display_name if aoi else a.aoi_id)) else a.aoi_id,
            aoi_country=aoi.country if aoi else "Global",
            aoi_region=aoi.region if aoi else "",
            domain_label=format_domain_label(a.domain),
            comparison_range_display=format_date_range(ev.comparison_start if ev else None, ev.comparison_end if ev else None),
            quality_gate_passed=a.quality.quality_gate_passed,
            quality_notes=a.quality.notes,
            primary_measurement_label=ev.primary_measurement_label if ev else None,
            primary_measurement_value=ev.primary_measurement_value if ev else None,
            validation_statement="Calibrated reference baseline verified" if val else "Calibrated baseline",
        ))

    # Build Insufficient Data Section
    insufficient_areas: list[InsufficientDataItem] = []
    for a in analyses:
        s_key = normalize_observation_state_key(a.observation_state)
        if s_key != "insufficient_data":
            continue

        aoi = aois.get(a.aoi_id)
        ev = events_by_analysis.get(a.id)

        insufficient_areas.append(InsufficientDataItem(
            analysis_id=a.id,
            event_id=ev.id if ev else None,
            event_url=f"/event/{ev.id}" if ev else None,
            map_url=f"/map?aoi={a.aoi_id}",
            lab_url=f"/lab/{a.id}",
            aoi_id=a.aoi_id,
            aoi_name=aooi_name if (aooi_name := (aoi.display_name if aoi else a.aoi_id)) else a.aoi_id,
            aoi_country=aoi.country if aoi else "Global",
            aoi_region=aoi.region if aoi else "",
            domain_label=format_domain_label(a.domain),
            comparison_range_display=format_date_range(ev.comparison_start if ev else None, None),
            valid_pixel_fraction_display=f"{a.quality.valid_pixel_fraction * 100:.1f}%",
            quality_failure_reason=a.quality.notes or "Valid SAR pixels below configured minimum.",
            available_context="Single pass reference available; repeat observation missing or degraded.",
        ))

    # Build Map Overview GeoJSON
    map_features: list[dict[str, Any]] = []
    for a in analyses:
        aoi = aois.get(a.aoi_id)
        if not aoi or not aoi.geometry:
            continue

        s_key = normalize_observation_state_key(a.observation_state)
        s_label, _ = format_observation_state(a.observation_state)
        ev = events_by_analysis.get(a.id)
        exp = exposures.get(a.id)
        situation = demo_service.get_situation_for_analysis(a.id)
        primary_situation_measurement = next(
            (item for item in (situation.direct_evidence if situation else []) if item.measurement_value is not None),
            None,
        )

        # Look up priority if scored
        queue_match = next((item for item in review_queue if item.analysis_id == a.id), None)

        props: dict[str, Any] = {
            "analysis_id": a.id,
            "aoi_id": a.aoi_id,
            "aoi_name": aoi.display_name,
            "aoi_country": aoi.country,
            "observation_state": s_key,
            "observation_state_label": s_label,
            # Scientific color tied strictly to Observation State, NOT Review Priority
            "observation_state_color": _get_observation_state_color(s_key),
            "domain_label": format_domain_label(a.domain),
            "interpretation": ev.title if ev else s_label,
            "human_headline": situation.headline if situation else s_label,
            "human_label": (situation.interpretations[0].public_label if situation and situation.interpretations else "Surface observation"),
            "comparison_dates": format_date_range(ev.comparison_start, ev.comparison_end) if ev else "Dates unavailable",
            "primary_measurement": (
                f"{primary_situation_measurement.measurement_name}: {primary_situation_measurement.measurement_value} {primary_situation_measurement.measurement_unit or ''}".strip()
                if primary_situation_measurement else "No primary measurement recorded"
            ),
            "exposure_data_available": False,
            "event_url": f"/event/{ev.id}" if ev else None,
            "lab_url": f"/lab/{a.id}",
        }

        if queue_match:
            props["review_priority_band"] = queue_match.priority.priority_band
            props["review_score"] = queue_match.priority.review_score
        else:
            props["review_priority_band"] = None
            props["review_score"] = None

        map_features.append({
            "type": "Feature",
            "geometry": aoi.geometry,
            "properties": props,
        })

    map_geojson = {
        "type": "FeatureCollection",
        "features": map_features,
    }

    review_queue_json = [item.model_dump() for item in review_queue]

    return DashboardDetailView(
        summary=summary,
        surface_changes=surface_changes,
        review_queue=review_queue,
        review_queue_json=review_queue_json,
        no_change_areas=no_change_areas,
        insufficient_areas=insufficient_areas,
        map_geojson=map_geojson,
    )
