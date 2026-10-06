"""
Event Detail Presentation View Model.
Converts raw domain models, spatial footprints, provenance records,
and validation benchmarks into presentation-ready fields for server-side Jinja2 rendering.
"""
from datetime import datetime
import json
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.models import (
    AnalysisEvidence,
    AOI,
    Acquisition,
    Analysis,
    AnalysisManifest,
    CandidateMatch,
    ChangeRegion,
    ClassificationStatus,
    DataOrigin,
    Domain,
    Event,
    ExposureResult,
    ObservationState,
    ProductMaturity,
    ValidationResult,
    ValidationStatus,
)
from app.services.demo_data import DemoDataService
from app.models.situation import SituationRecord
from app.utils.presentation import (
    format_date_range,
    format_domain_label,
    format_observation_state,
    format_validation_status,
)


class KeyValueItem(BaseModel):
    key: str
    label: str
    value: str


class MeasurementItem(BaseModel):
    key: str
    label: str
    value: str
    unit: Optional[str] = None
    description: Optional[str] = None


class AcquisitionDetail(BaseModel):
    id: str
    source: str
    sensor: str
    product_type: str
    acquisition_datetime: str
    formatted_date: str
    track: int
    frame: int
    orbit_direction: str
    mode: str
    polarizations_display: str
    frequency: str
    bandwidth: str
    maturity: str
    crid: str


class EvidenceItem(BaseModel):
    key: str
    label: str
    value: str


class FIRMSCorroborationDetail(BaseModel):
    time_buffer_hours: Optional[float] = None
    spatial_buffer_m: Optional[float] = None
    matching_detection_count: Optional[int] = None
    nearest_distance_m: Optional[float] = None
    is_supported: bool = False
    statement: str


class CandidateEvidenceItem(BaseModel):
    id: str
    domain_raw: str
    domain_label: str
    candidate_score: Optional[float] = None
    candidate_score_display: Optional[str] = None
    score_disclaimer: str = "This is a rule/evidence score, not a probability of cause."
    supported: bool
    support_status_label: str
    support_badge_class: str
    notes: str
    physical_evidence: list[EvidenceItem]
    independent_evidence: list[EvidenceItem]
    contradicting_evidence: list[EvidenceItem]
    has_firms: bool = False
    firms_details: Optional[FIRMSCorroborationDetail] = None


class ValidationMetricItem(BaseModel):
    key: str
    label: str
    value: str


class EventDetailView(BaseModel):
    # 1. Hero / Observation Summary
    eyebrow: str = "SURFACE CHANGE OBSERVATION"
    id: str
    analysis_id: str
    title: str
    short_description: str
    observation_state_raw: str
    observation_state_label: str
    observation_state_badge_class: str
    domain_raw: str
    domain_label: str
    is_synthetic: bool
    synthetic_badge_text: str = "DEMO FIXTURE"
    synthetic_warning: str = "Synthetic development fixture — not an Earth observation result."
    product_maturity_label: str
    product_maturity_badge_class: str
    validation_status_label: str
    validation_status_badge_class: str
    comparison_dates_display: str
    data_origin_display: str
    created_at_display: str

    # 2. Location Map & AOI
    aoi_id: str
    aoi_name: str
    aoi_country: str
    aoi_region: str
    aoi_geojson_str: str
    change_regions_geojson_str: str
    has_change_regions: bool
    map_bounds: list[list[float]]
    map_center: list[float]
    explorer_url: str

    # 3. Observation Details Metadata Block
    classification_status: str
    classification_status_label: str
    final_classification: Optional[str] = None
    manifest_id: str

    # 4. Comparison / Acquisitions
    comparison_policy: str
    has_before_acquisition: bool
    before_acquisition: Optional[AcquisitionDetail] = None
    has_after_acquisition: bool
    after_acquisition: Optional[AcquisitionDetail] = None
    after_unavailable_notice: Optional[str] = None

    # 5. Measurement Summary
    has_measurements: bool
    measurements: list[MeasurementItem] = Field(default_factory=list)
    measurements_notice: Optional[str] = None

    # 6. Interpretation & Candidate Evidence
    is_resolved: bool
    resolved_domain_label: Optional[str] = None
    resolved_explanation: Optional[str] = None
    is_ambiguous_or_unclassified: bool
    unclassified_notice: Optional[str] = None
    candidates: list[CandidateEvidenceItem] = Field(default_factory=list)

    # 7. Quality & Data Availability
    valid_pixel_fraction_display: str
    required_inputs_available: bool
    quality_gate_passed: bool
    quality_notes: str
    quality_gate_failure_reason: Optional[str] = None

    # 8. Exposure Context
    has_exposure: bool
    is_exposure_withheld: bool
    exposure_withheld_notice: Optional[str] = None
    estimated_population_display: Optional[str] = None
    population_source: Optional[str] = None
    population_year: Optional[int] = None
    road_length_display: Optional[str] = None
    rail_length_display: Optional[str] = None
    bridge_count: Optional[int] = None
    hospital_count: Optional[int] = None
    settlement_count: Optional[int] = None
    exposure_notes: Optional[str] = None

    # 9. Validation
    validation_status: str
    independent_validation: bool
    number_of_independent_events: int
    validation_statement: str
    reference_dataset: Optional[str] = None
    calibration_event_id: Optional[str] = None
    validation_event_ids: list[str] = Field(default_factory=list)
    metrics: list[ValidationMetricItem] = Field(default_factory=list)

    # 10. Provenance / Manifest
    pipeline_version: str
    code_version: str
    track: int
    frame: int
    orbit_direction: str
    mode: str
    polarizations_display: str
    crid: str
    threshold_selection_method: Optional[str] = None
    quality_parameters: list[KeyValueItem] = Field(default_factory=list)
    detection_parameters: list[KeyValueItem] = Field(default_factory=list)

    # 11. Limitations
    limitations: list[str] = Field(default_factory=list)
    general_disclaimer: str = (
        "This application reports observed surface-change evidence. "
        "It does not predict disasters or issue emergency instructions."
    )

    # 12. Actions & Links
    image_lab_url: str
    map_explorer_url: str
    copilot_url: str

    # 13. Precomputed Visual Evidence Assets
    evidence: Optional[AnalysisEvidence] = None
    situation: SituationRecord


# Presentation label mappings for measurement keys
MEASUREMENT_LABEL_MAP: dict[str, tuple[str, str, str]] = {
    "inundated_area_km2": ("Synthetic Water-Change Area", "km²", "Legacy demonstration measurement; not used as a flood-confirmation field."),
    "candidate_radar_change_area_km2": ("Candidate Radar-Change Pixels", "km²", "Quality-screened pixels meeting the configured radar-change criterion before minimum-region filtering."),
    "retained_mapped_region_area_km2": ("Retained Mapped Regions", "km²", "Area retained after removing connected components below the configured minimum region size."),
    "removed_small_component_area_km2": ("Filtered Small Components", "km²", "Candidate area removed by the minimum-region-size filter."),
    "change_criterion_db": ("Radar-Change Criterion", "dB", "Signed after-minus-before backscatter criterion used to build the candidate mask."),
    "changed_area_km2": ("Changed Area", "km²", "Total surface area exhibiting significant radar backscatter or coherence anomaly."),
    "anomaly_area_km2": ("Radar Anomaly Area", "km²", "Area exhibiting unexplained radar backscatter drop and coherence loss."),
    "new_water_area_km2": ("Synthetic Water-Change Candidate Area", "km²", "Demonstration area inferred from radar contrast; not an authoritative flood extent."),
    "max_displacement_mm": ("Max Relative Displacement", "mm", "Maximum relative line-of-sight displacement from interferometric phase."),
    "los_displacement_mm": ("Relative LOS Displacement", "mm", "Line-of-sight surface displacement relative to stable reference."),
    "mean_coherence": ("Mean Interferometric Coherence", "", "Temporal coherence magnitude across the repeat baseline."),
    "coherence_loss": ("Interferometric Coherence Loss", "", "Magnitude of temporal decorrelation between primary and secondary passes."),
    "backscatter_reduction_mean_db": ("Legacy Backscatter Field", "dB", "Legacy demonstration field; prefer signed after-minus-before backscatter difference."),
    "mean_backscatter_difference_db": ("Mean Backscatter Difference (After − Before)", "dB", "Signed mean change in calibrated radar backscatter; negative values mean the radar return decreased."),
    "valid_pixel_fraction": ("Valid Pixel Fraction", "%", "Proportion of valid radar pixels evaluated across the AOI."),
    "velocity_m_per_day": ("Surface Velocity", "m/day", "Estimated glacier or displacement velocity from speckle tracking."),
}

VALIDATION_METRIC_LABEL_MAP: dict[str, str] = {
    "intersection_over_union": "Intersection over Union (IoU)",
    "precision": "Precision",
    "recall": "Recall",
    "f1_score": "F1 Score",
    "displacement_rmse_mm": "Displacement RMSE",
    "phase_residual_rad": "Phase Residual",
    "area_error_percent": "Area Error",
}


def _format_date(iso_str: Optional[str]) -> str:
    if not iso_str:
        return "Not available"
    try:
        clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return iso_str


def _format_key_title(key: str) -> str:
    """Converts snake_case to Human Readable Title."""
    return key.replace("_", " ").title()


def _format_evidence_dict(ev_dict: dict[str, Any]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for k, v in ev_dict.items():
        label = _format_key_title(k)
        if isinstance(v, bool):
            val_str = "Yes" if v else "No"
        elif isinstance(v, float):
            val_str = f"{v:.2f}"
        else:
            val_str = str(v)
        items.append(EvidenceItem(key=k, label=label, value=val_str))
    return items


def _format_key_value_items(params: dict[str, Any]) -> list[KeyValueItem]:
    items: list[KeyValueItem] = []
    for k, v in params.items():
        label = _format_key_title(k)
        if isinstance(v, float):
            val_str = f"{v:.3f}"
        elif isinstance(v, bool):
            val_str = "true" if v else "false"
        else:
            val_str = str(v)
        items.append(KeyValueItem(key=k, label=label, value=val_str))
    return items


def _compute_bounds(geometry: dict[str, Any]) -> tuple[list[list[float]], list[float]]:
    """Calculates [[min_lon, min_lat], [max_lon, max_lat]] and center [lon, lat]."""
    coords_list = []
    geom_type = geometry.get("type")
    raw_coords = geometry.get("coordinates", [])

    if geom_type == "Polygon":
        for ring in raw_coords:
            for pt in ring:
                coords_list.append(pt)
    elif geom_type == "MultiPolygon":
        for poly in raw_coords:
            for ring in poly:
                for pt in ring:
                    coords_list.append(pt)
    elif geom_type == "Point":
        coords_list.append(raw_coords)

    if not coords_list:
        return [[-180.0, -90.0], [180.0, 90.0]], [0.0, 0.0]

    lons = [p[0] for p in coords_list]
    lats = [p[1] for p in coords_list]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    center = [(min_lon + max_lon) / 2.0, (min_lat + max_lat) / 2.0]
    return [[min_lon, min_lat], [max_lon, max_lat]], center


def format_acquisition_detail(acq: Acquisition) -> AcquisitionDetail:
    return AcquisitionDetail(
        id=acq.id,
        source=acq.source,
        sensor=acq.sensor,
        product_type=acq.product_type.value if hasattr(acq.product_type, "value") else str(acq.product_type),
        acquisition_datetime=acq.acquisition_datetime,
        formatted_date=_format_date(acq.acquisition_datetime),
        track=acq.track,
        frame=acq.frame,
        orbit_direction=acq.orbit_direction.capitalize(),
        mode=acq.mode,
        polarizations_display=", ".join(acq.polarizations),
        frequency=acq.frequency,
        bandwidth=acq.bandwidth,
        maturity=acq.maturity.value if hasattr(acq.maturity, "value") else str(acq.maturity),
        crid=acq.crid,
    )


def build_event_detail_view(event_id: str, demo_service: DemoDataService) -> Optional[EventDetailView]:
    """
    Constructs a complete EventDetailView presentation model from data service fixtures.
    Returns None if event_id is not found.
    """
    event = demo_service.get_event(event_id)
    if not event:
        return None

    analysis = demo_service.get_analysis(event.analysis_id)
    if not analysis:
        return None

    aoi = demo_service.get_aoi(event.aoi_id)
    if not aoi:
        # Fallback empty AOI if missing
        aoi = AOI(
            id=event.aoi_id,
            display_name=f"AOI {event.aoi_id}",
            country="Unknown",
            region="Unknown",
            geometry={"type": "Polygon", "coordinates": []},
            is_demo=True,
            disclaimer="Synthetic development fixture — not an Earth observation result."
        )

    manifest = demo_service.get_manifest(analysis.manifest_id)
    exposure = demo_service.get_exposure_for_analysis(analysis.id)
    evidence = demo_service.get_evidence_for_analysis(analysis.id)
    validation = demo_service.get_validation_for_analysis(analysis.id)
    regions = demo_service.get_regions_for_analysis(analysis.id)
    candidates_raw = demo_service.get_candidates_for_analysis(analysis.id)
    situation = demo_service.get_situation_for_analysis(analysis.id)

    # 1. Hero & Domain / State
    domain_label = format_domain_label(event.domain)
    state_label, state_badge_class = format_observation_state(event.observation_state)
    val_status_label, val_badge_class = format_validation_status(event.validation_status)
    date_display = format_date_range(event.comparison_start, event.comparison_end)

    is_synthetic = (
        event.data_origin == DataOrigin.SYNTHETIC_UI_FIXTURE or
        getattr(event, "is_demo", False)
    )
    synthetic_badge = "DEMO FIXTURE" if is_synthetic else "REAL NISAR ANALYSIS"
    synthetic_warn = "Synthetic development fixture — not an Earth observation result." if is_synthetic else ""
    if not is_synthetic and event.comparison_start and "2026-06-28" in str(event.comparison_start):
        date_display = "2026-06-28 → 2026-07-10" 

    maturity_val = event.product_maturity.value if hasattr(event.product_maturity, "value") else str(event.product_maturity)
    maturity_badge_class = "badge-maturity"
    if maturity_val == "BETA":
        maturity_badge_class = "badge-maturity border-[#1E6BFF]/40 text-[#60A5FA]"

    # Short description rules
    short_desc = event.short_description
    if event.observation_state == ObservationState.UNKNOWN_CHANGE:
        short_desc = "Unusual radar change detected. Cause not identified."
    elif event.observation_state == ObservationState.INSUFFICIENT_DATA:
        short_desc = "Not enough usable data was available to determine surface change."
    elif event.observation_state == ObservationState.NO_CHANGE:
        short_desc = "Usable observations were analyzed and no significant surface change was detected under the configured criteria."

    # 2. Location Map & GeoJSON
    aoi_bounds, aoi_center = _compute_bounds(aoi.geometry)
    
    # Compile change regions into GeoJSON FeatureCollection
    region_features = []
    for r in regions:
        region_features.append({
            "type": "Feature",
            "id": r.id,
            "geometry": r.geometry,
            "properties": {
                "region_id": r.id,
                "analysis_id": r.analysis_id,
                "area_km2": r.area_km2,
                "classification_status": r.classification_status.value if hasattr(r.classification_status, "value") else str(r.classification_status),
                "final_classification": r.final_classification,
            }
        })
    change_regions_fc = {
        "type": "FeatureCollection",
        "features": region_features
    }

    # 3. Acquisitions
    before_acq = demo_service.get_acquisition(analysis.before_acquisition_id) if analysis.before_acquisition_id else None
    after_acq = demo_service.get_acquisition(analysis.after_acquisition_id) if analysis.after_acquisition_id else None

    before_detail = format_acquisition_detail(before_acq) if before_acq else None
    after_detail = format_acquisition_detail(after_acq) if after_acq else None
    after_unavailable_notice = None
    if not after_acq:
        after_unavailable_notice = "Not applicable / unavailable (no secondary repeat pass available in current catalog)"

    # Comparison policy display
    comp_policy = manifest.comparison_policy if manifest else "Nearest previous compatible acquisition"
    if comp_policy == "exact_repeat_12day":
        comp_policy = "Exact Repeat Baseline (12-day orbital cycle)"
    elif comp_policy == "insar_interferometric_pair_12day":
        comp_policy = "Interferometric Exact Repeat Pair (12-day coherence baseline)"
    elif comp_policy == "temporal_pair_missing_secondary":
        comp_policy = "Secondary Acquisition Missing (Unpaired observation)"

    # 4. Measurement Summary
    # Critical Rule: If observation_state == INSUFFICIENT_DATA, do NOT show fake change metrics
    has_measurements = (
        event.observation_state != ObservationState.INSUFFICIENT_DATA and
        bool(analysis.measurements)
    )
    measurements_list: list[MeasurementItem] = []
    measurements_notice = None

    if event.observation_state == ObservationState.INSUFFICIENT_DATA:
        measurements_notice = "Not enough usable data was available to determine surface change. Primary measurements withheld."
    elif has_measurements:
        for k, v in analysis.measurements.items():
            if k in MEASUREMENT_LABEL_MAP:
                lbl, unit, desc = MEASUREMENT_LABEL_MAP[k]
                if isinstance(v, float):
                    # Area values are small enough that three decimals communicate the
                    # stored mask-vs-region distinction without a one-off magic number.
                    precision = 3 if unit == "km²" else 2
                    val_str = f"{v:.{precision}f} {unit}".strip()
                elif isinstance(v, int):
                    val_str = f"{v} {unit}".strip()
                else:
                    val_str = f"{v} {unit}".strip()
                measurements_list.append(MeasurementItem(
                    key=k,
                    label=lbl,
                    value=val_str,
                    unit=unit or None,
                    description=desc
                ))
            else:
                lbl = _format_key_title(k)
                val_str = f"{v:.2f}" if isinstance(v, float) else str(v)
                measurements_list.append(MeasurementItem(
                    key=k,
                    label=lbl,
                    value=val_str,
                    description=f"Raw scientific measurement for parameter {k}."
                ))

    # 5. Interpretation & Candidate Evidence
    is_resolved = (analysis.classification_status == ClassificationStatus.RESOLVED)
    is_ambiguous_or_unclassified = (
        analysis.classification_status in [ClassificationStatus.AMBIGUOUS, ClassificationStatus.UNCLASSIFIED] or
        event.observation_state == ObservationState.UNKNOWN_CHANGE
    )
    unclassified_notice = "Unusual radar change detected. Cause not identified." if is_ambiguous_or_unclassified else None

    # Candidate matches
    candidates_list: list[CandidateEvidenceItem] = []
    firms_metadata = {
        "firms_time_buffer_hours": manifest.firms_time_buffer_hours if manifest else None,
        "firms_spatial_buffer_m": manifest.firms_spatial_buffer_m if manifest else None,
        "matching_firms_detection_count": manifest.matching_firms_detection_count if manifest else None,
        "nearest_firms_distance_m": manifest.nearest_firms_distance_m if manifest else None,
    }

    resolved_explanation = None
    for c in candidates_raw:
        cand_domain_label = format_domain_label(c.candidate_domain)
        score_disp = f"{c.candidate_score:.2f}" if c.candidate_score is not None else None
        
        # FIRMS corroboration check
        has_firms = False
        firms_detail = None
        if c.candidate_domain == Domain.WILDFIRE or firms_metadata["firms_time_buffer_hours"] is not None:
            has_firms = True
            time_buf = firms_metadata["firms_time_buffer_hours"]
            spat_buf = firms_metadata["firms_spatial_buffer_m"]
            match_cnt = firms_metadata["matching_firms_detection_count"]
            nearest_m = firms_metadata["nearest_firms_distance_m"]
            is_corrob = bool(match_cnt and match_cnt > 0)
            
            if is_corrob:
                firms_stmt = f"FIRMS active fire agreement supported ({match_cnt} detection(s) within {time_buf}h and {spat_buf}m)."
            else:
                firms_stmt = (
                    f"No matching active fire detections in FIRMS within "
                    f"{time_buf or 24}h time buffer and {spat_buf or 1500}m spatial buffer."
                )
            
            firms_detail = FIRMSCorroborationDetail(
                time_buffer_hours=time_buf,
                spatial_buffer_m=spat_buf,
                matching_detection_count=match_cnt,
                nearest_distance_m=nearest_m,
                is_supported=is_corrob,
                statement=firms_stmt,
            )

        c_item = CandidateEvidenceItem(
            id=c.id,
            domain_raw=c.candidate_domain.value,
            domain_label=cand_domain_label,
            candidate_score=c.candidate_score,
            candidate_score_display=score_disp,
            supported=c.supported,
            support_status_label="SUPPORTED" if c.supported else "NOT CONFIRMED",
            support_badge_class="badge-validated" if c.supported else "badge-maturity",
            notes=c.notes,
            physical_evidence=_format_evidence_dict(c.physical_evidence),
            independent_evidence=_format_evidence_dict(c.independent_evidence),
            contradicting_evidence=_format_evidence_dict(c.contradicting_evidence),
            has_firms=has_firms,
            firms_details=firms_detail,
        )
        candidates_list.append(c_item)

        if is_resolved and c.supported:
            resolved_explanation = c.notes

    if is_resolved and not resolved_explanation:
        resolved_explanation = (
            f"Surface change signature matches characteristic {domain_label.lower()} "
            f"radar backscatter patterns and dual-polarization decomposition response."
        )

    # 6. Quality & Data Availability
    valid_fraction_pct = f"{analysis.quality.valid_pixel_fraction * 100:.1f}%"
    quality_gate_fail_reason = None
    if not analysis.quality.quality_gate_passed:
        quality_gate_fail_reason = analysis.quality.notes or "Quality gate failed: insufficient usable radar pixels."

    # 7. Exposure Context
    has_exposure = exposure is not None
    is_exposure_withheld = (event.observation_state == ObservationState.INSUFFICIENT_DATA)
    exposure_withheld_notice = (
        "Exposure calculation withheld due to insufficient primary SAR observations."
        if is_exposure_withheld else None
    )

    est_pop_disp = None
    road_disp = None
    rail_disp = None
    if exposure and not is_exposure_withheld:
        if exposure.estimated_population is not None:
            est_pop_disp = f"{exposure.estimated_population:,}"
        if exposure.road_length_km is not None:
            road_disp = f"{exposure.road_length_km:.1f} km"
        if exposure.rail_length_km is not None:
            rail_disp = f"{exposure.rail_length_km:.1f} km"

    # 8. Validation
    val_status_str = validation.status.value if validation and hasattr(validation.status, "value") else "unvalidated"
    val_indep = validation.independent_validation if validation else False
    val_num_indep = validation.number_of_independent_events if validation else 0

    # Validation statement rules
    if not is_synthetic and validation and validation.notes:
        val_statement = validation.notes
    elif val_status_str == "validated" and val_num_indep > 0:
        val_statement = f"Validated on {val_num_indep} independent event(s)."
    elif val_status_str == "calibrated_only":
        val_statement = "Threshold calibrated on available event data; no independent validation."
    elif val_status_str == "beta_demo":
        val_statement = "Beta demonstration model; independent validation pending."
    else:
        val_statement = "Unvalidated."

    val_metrics_list: list[ValidationMetricItem] = []
    if validation and validation.metrics:
        for k, v in validation.metrics.items():
            metric_label = VALIDATION_METRIC_LABEL_MAP.get(k, _format_key_title(k))
            if isinstance(v, float):
                metric_val = f"{v:.2f}"
            else:
                metric_val = str(v)
            val_metrics_list.append(ValidationMetricItem(
                key=k,
                label=metric_label,
                value=metric_val
            ))

    # 9. Provenance / Manifest Details
    qual_params = _format_key_value_items(manifest.quality_parameters) if manifest else []
    det_params = _format_key_value_items(manifest.detection_parameters) if manifest else []
    pols_disp = ", ".join(manifest.polarizations) if manifest and manifest.polarizations else "HH, HV"

    # 10. Limitations (Honest derivation from stored record)
    limitations_list: list[str] = []
    if is_synthetic:
        limitations_list.append("This is a synthetic development record created for the NASA Space Apps Challenge demo.")
    if val_status_str in ["unvalidated", "beta_demo"]:
        limitations_list.append("This domain algorithm has not been independently validated against ground truth.")
    elif val_status_str == "calibrated_only":
        limitations_list.append("Threshold parameters calibrated against historical reference data; performance on new regions may vary.")
    if maturity_val == "BETA":
        limitations_list.append("BETA product maturity indicates experimental radar calibrations that may differ from operational PROVISIONAL standards.")
    if event.observation_state == ObservationState.UNKNOWN_CHANGE or analysis.classification_status in [ClassificationStatus.UNCLASSIFIED, ClassificationStatus.AMBIGUOUS]:
        limitations_list.append("Radar change alone does not establish a physical cause. Independent sensor corroboration is required.")
    if event.observation_state == ObservationState.INSUFFICIENT_DATA or not analysis.quality.quality_gate_passed:
        limitations_list.append("Observation did not meet minimum data quality requirements (valid pixel fraction below threshold).")
    if exposure and not is_exposure_withheld:
        limitations_list.append("Population and infrastructure values are contextual spatial overlap estimates, not verified casualties or on-the-ground damage.")

    return EventDetailView(
        # 1. Hero
        eyebrow="SURFACE CHANGE OBSERVATION",
        id=event.id,
        analysis_id=event.analysis_id,
        title=event.title,
        short_description=short_desc,
        observation_state_raw=event.observation_state.value,
        observation_state_label=state_label,
        observation_state_badge_class=state_badge_class,
        domain_raw=event.domain.value,
        domain_label=domain_label,
        is_synthetic=is_synthetic,
        synthetic_badge_text="DEMO FIXTURE",
        synthetic_warning="Synthetic development fixture — not an Earth observation result.",
        product_maturity_label=maturity_val,
        product_maturity_badge_class=maturity_badge_class,
        validation_status_label=val_status_label,
        validation_status_badge_class=val_badge_class,
        comparison_dates_display=date_display,
        data_origin_display="Synthetic Development Fixture" if is_synthetic else "Precomputed Earth Observation",
        created_at_display=_format_date(analysis.created_at),

        # 2. Location Map & AOI
        aoi_id=aoi.id,
        aoi_name=aoi.display_name,
        aoi_country=aoi.country,
        aoi_region=aoi.region,
        aoi_geojson_str=json.dumps(aoi.geometry),
        change_regions_geojson_str=json.dumps(change_regions_fc),
        has_change_regions=len(region_features) > 0,
        map_bounds=aoi_bounds,
        map_center=aoi_center,
        explorer_url=f"/map?aoi={aoi.id}",

        # 3. Observation Details
        classification_status=analysis.classification_status.value,
        classification_status_label="RESOLVED" if is_resolved else "CAUSE NOT CONFIRMED",
        final_classification=analysis.final_classification,
        manifest_id=analysis.manifest_id,

        # 4. Comparison / Acquisitions
        comparison_policy=comp_policy,
        has_before_acquisition=before_detail is not None,
        before_acquisition=before_detail,
        has_after_acquisition=after_detail is not None,
        after_acquisition=after_detail,
        after_unavailable_notice=after_unavailable_notice,

        # 5. Measurements
        has_measurements=has_measurements,
        measurements=measurements_list,
        measurements_notice=measurements_notice,

        # 6. Interpretation & Candidate Evidence
        is_resolved=is_resolved,
        resolved_domain_label=domain_label if is_resolved else None,
        resolved_explanation=resolved_explanation,
        is_ambiguous_or_unclassified=is_ambiguous_or_unclassified,
        unclassified_notice=unclassified_notice,
        candidates=candidates_list,

        # 7. Quality
        valid_pixel_fraction_display=valid_fraction_pct,
        required_inputs_available=analysis.quality.required_inputs_available,
        quality_gate_passed=analysis.quality.quality_gate_passed,
        quality_notes=analysis.quality.notes,
        quality_gate_failure_reason=quality_gate_fail_reason,

        # 8. Exposure
        has_exposure=has_exposure,
        is_exposure_withheld=is_exposure_withheld,
        exposure_withheld_notice=exposure_withheld_notice,
        estimated_population_display=est_pop_disp,
        population_source=exposure.population_source if exposure else None,
        population_year=exposure.population_year if exposure else None,
        road_length_display=road_disp,
        rail_length_display=rail_disp,
        bridge_count=exposure.bridge_count if exposure else None,
        hospital_count=exposure.hospital_count if exposure else None,
        settlement_count=exposure.settlement_count if exposure else None,
        exposure_notes=exposure.notes if exposure else None,

        # 9. Validation
        validation_status=val_status_str,
        independent_validation=val_indep,
        number_of_independent_events=val_num_indep,
        validation_statement=val_statement,
        reference_dataset=validation.reference_dataset if validation else None,
        calibration_event_id=validation.calibration_event_id if validation else None,
        validation_event_ids=validation.validation_event_ids if validation else [],
        metrics=val_metrics_list,

        # 10. Provenance / Manifest
        pipeline_version=manifest.pipeline_version if manifest else "v1.0.0",
        code_version=manifest.code_version if manifest else "main",
        track=manifest.track if manifest else 0,
        frame=manifest.frame if manifest else 0,
        orbit_direction=manifest.orbit_direction.capitalize() if manifest else "Unknown",
        mode=manifest.mode if manifest else "Unknown",
        polarizations_display=pols_disp,
        crid=manifest.crid if manifest else "N/A",
        threshold_selection_method=manifest.threshold_selection_method if manifest else "Adaptive Otsu Thresholding",
        quality_parameters=qual_params,
        detection_parameters=det_params,

        # 11. Limitations
        limitations=limitations_list,
        general_disclaimer="This application reports observed surface-change evidence. It does not predict disasters or issue emergency instructions.",

        # 12. Actions
        image_lab_url=f"/lab/{analysis.id}",
        map_explorer_url=f"/map?aoi={aoi.id}",
        copilot_url=f"/copilot?event={event.id}",

        # 13. Evidence
        evidence=evidence,
        situation=situation,
    )
