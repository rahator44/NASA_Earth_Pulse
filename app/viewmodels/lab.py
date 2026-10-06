"""
Lab Detail Presentation View Model for Scientist Image Lab.
Packages stored analysis, visual evidence, precomputed distributions,
threshold previews, provenance parameters, and validation benchmarks
into a presentation model for /lab/{analysis_id}.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.models import (
    Analysis,
    AnalysisEvidence,
    AnalysisLabMetrics,
    DataOrigin,
    HistogramData,
    ThresholdPreview,
)
from app.services.demo_data import DemoDataService
from app.utils.presentation import (
    format_domain_label,
    format_observation_state,
    format_validation_status,
)
from app.viewmodels.event_detail import (
    AcquisitionDetail,
    KeyValueItem,
    ValidationMetricItem,
    _format_date,
    _format_key_title,
    _format_key_value_items,
    format_acquisition_detail,
)


class LabDetailView(BaseModel):
    analysis_id: str
    target_id: str
    title: str
    aoi_id: str
    aoi_name: str
    aoi_country: str
    aoi_region: str
    domain_raw: str
    domain_label: str
    observation_state_raw: str
    observation_state_label: str
    observation_state_badge_class: str
    classification_status_label: str
    product_maturity_label: str
    product_maturity_badge_class: str
    validation_status_label: str
    validation_status_badge_class: str
    manifest_id: str
    is_synthetic: bool = True
    synthetic_badge_text: str = "DEMO LAB"
    synthetic_warning: str = (
        "Synthetic evidence and analysis controls are used to demonstrate "
        "the scientist workflow. These are not NISAR measurements."
    )

    # Navigation Links
    event_id: Optional[str] = None
    event_url: Optional[str] = None
    map_url: str

    # Core Visual Evidence (Step 8 Viewer)
    evidence: Optional[AnalysisEvidence] = None

    # Exploratory Lab Metrics
    lab_metrics: Optional[AnalysisLabMetrics] = None
    has_lab_metrics: bool = False
    active_channel: str = "HH"
    available_channels: list[str] = Field(default_factory=list)
    channel_label: str = "HH"
    has_multiple_channels: bool = False

    # Precomputed Distribution / Histogram
    has_histogram: bool = False
    histogram: Optional[HistogramData] = None

    # Precomputed Threshold Preview
    has_threshold_preview: bool = False
    threshold_preview: Optional[ThresholdPreview] = None

    # Quality Evaluation
    quality_gate_passed: bool = True
    quality_notes: str = ""
    valid_pixel_fraction_display: str = "100%"
    has_quality_mask: bool = False
    quality_mask_url: Optional[str] = None
    pixel_value_summary: Optional[str] = None

    # Method Explanation Steps
    method_steps: list[str] = Field(default_factory=list)

    # Acquisitions
    before_acquisition: Optional[AcquisitionDetail] = None
    after_acquisition: Optional[AcquisitionDetail] = None

    # Manifest Parameters
    quality_parameters: list[KeyValueItem] = Field(default_factory=list)
    detection_parameters: list[KeyValueItem] = Field(default_factory=list)
    pipeline_version: str = "v1.0.0"
    code_version: str = "main"
    comparison_policy: str = "Standard repeat"
    threshold_selection_method: str = "Configured"

    # Validation
    validation_status: str = "unvalidated"
    independent_validation: bool = False
    number_of_independent_events: int = 0
    validation_statement: str = "Unvalidated."
    reference_dataset: Optional[str] = None
    metrics: list[ValidationMetricItem] = Field(default_factory=list)

    # Scientific Limitations
    limitations: list[str] = Field(default_factory=list)


def build_lab_detail_view(analysis_id: str, demo_service: DemoDataService) -> Optional[LabDetailView]:
    """
    Constructs a complete LabDetailView presentation model from data service fixtures.
    Returns None if analysis is not found.
    """
    # Support 'demo' alias for backward compatibility
    target_id = "analysis_synth_001" if analysis_id == "demo" else analysis_id

    analysis = demo_service.get_analysis(target_id)
    if not analysis:
        return None

    aoi = demo_service.get_aoi(analysis.aoi_id)
    aoi_name = aoi.display_name if aoi else f"AOI {analysis.aoi_id}"
    aoi_country = aoi.country if aoi else "Global"
    aoi_region = aoi.region if aoi else "Study Area"

    manifest = demo_service.get_manifest(analysis.manifest_id)
    evidence = demo_service.get_evidence_for_analysis(target_id)
    lab_metrics = demo_service.get_lab_metrics_for_analysis(target_id)
    validation = demo_service.get_validation_for_analysis(target_id)

    # Linked Event if any
    linked_events = demo_service.get_events_for_analysis(target_id)
    linked_event = linked_events[0] if linked_events else None

    # Observation and Domain labels
    domain_label = format_domain_label(analysis.domain)
    state_label, state_badge_class = format_observation_state(analysis.observation_state)
    val_status_str = validation.status.value if validation and hasattr(validation.status, "value") else "unvalidated"
    val_label, val_badge_class = format_validation_status(val_status_str)

    # Product Maturity
    maturity_val = manifest.maturity.value if manifest and hasattr(manifest.maturity, "value") else "PROVISIONAL"
    maturity_badge_class = "badge-maturity"
    if maturity_val == "BETA":
        maturity_badge_class = "badge-maturity border-[#1E6BFF]/40 text-[#60A5FA]"

    # Acquisitions
    before_acq = demo_service.get_acquisition(analysis.before_acquisition_id) if analysis.before_acquisition_id else None
    after_acq = demo_service.get_acquisition(analysis.after_acquisition_id) if analysis.after_acquisition_id else None
    before_detail = format_acquisition_detail(before_acq) if before_acq else None
    after_detail = format_acquisition_detail(after_acq) if after_acq else None

    # Manifest Key-Value Parameters
    qual_params = _format_key_value_items(manifest.quality_parameters) if manifest else []
    det_params = _format_key_value_items(manifest.detection_parameters) if manifest else []

    # Validation
    val_indep = validation.independent_validation if validation else False
    val_num_indep = validation.number_of_independent_events if validation else 0
    if val_status_str == "validated" and val_num_indep > 0:
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
            metric_label = _format_key_title(k)
            metric_val = f"{v:.2f}" if isinstance(v, float) else str(v)
            val_metrics_list.append(ValidationMetricItem(key=k, label=metric_label, value=metric_val))

    # Channels
    channels = lab_metrics.available_channels if lab_metrics and lab_metrics.available_channels else ["HH"]
    active_chan = lab_metrics.active_channel if lab_metrics else channels[0]
    chan_label = lab_metrics.channel_label if lab_metrics and lab_metrics.channel_label else f"{active_chan} Channel"

    # Threshold Preview & Histogram Rules
    # Rule: If quality_gate_passed = false, do NOT provide threshold controls
    has_threshold = False
    thresh_preview = None
    if analysis.quality.quality_gate_passed and lab_metrics and lab_metrics.threshold_preview:
        has_threshold = True
        thresh_preview = lab_metrics.threshold_preview

    has_hist = False
    hist_data = None
    if analysis.quality.quality_gate_passed and lab_metrics and lab_metrics.histogram:
        has_hist = True
        hist_data = lab_metrics.histogram

    # Method Explanation Steps (Domain-aware)
    if "wetland" in analysis.domain.value or "flood" in analysis.domain.value:
        method_steps = [
            "1. Co-register dual-pol L-band SAR acquisitions across 12-day orbital baseline.",
            "2. Evaluate radiometrically terrain-corrected backscatter valid pixel fraction (Quality Gate: ≥ 85%).",
            "3. Compute temporal log-ratio backscatter difference raster (Δγ° in dB).",
            "4. Apply adaptive bimodal thresholding (nominal: -3.8 dB) to segment specular open water reflection.",
            "5. Apply spatial contiguous component filtering to eliminate radar speckle false positives.",
            "6. Delineate vector change polygons and corroborate with independent water gauge concordance."
        ]
    elif "deformation" in analysis.domain.value:
        method_steps = [
            "1. Ingest interferometric single-look complex (GUNW) SLC pair across 12-day baseline.",
            "2. Filter interferometric phase fringes and compute normalized coherence magnitude.",
            "3. Evaluate phase residual stability over known geodetic bedrock control network.",
            "4. Verify zero macro displacement threshold (< 2.0 mm noise baseline).",
            "5. Report stable geodetic reference without false deformation alerts."
        ]
    else:
        method_steps = [
            "1. Ingest multi-temporal radar backscatter and coherence products.",
            "2. Evaluate quality gates and valid pixel availability.",
            "3. Compute cross-channel anomaly divergence metrics.",
            "4. Match candidate physical hypotheses against radar decomposition characteristics.",
            "5. Evaluate independent sensor concordance (e.g. thermal active fire corroboration).",
            "6. Preserve unclassified state when multi-sensor evidence diverges."
        ]

    is_synthetic = (analysis.data_origin == DataOrigin.SYNTHETIC_UI_FIXTURE or getattr(analysis, "is_demo", False))

    # Limitations
    if is_synthetic:
        limitations = [
            "Synthetic visual and metric fixtures are used to demonstrate the scientist workflow.",
            "Numeric pixel sampling is disabled; raster pixel values become queryable with real COG endpoints.",
            "Threshold preview operates on precomputed discrete preview states and does not re-execute the radar processing pipeline.",
            "Atmospheric phase delay screens have not been modeled in this demonstration.",
        ]
    else:
        limitations = [
            "Ingests operational L2 GCOV / GUNW backscatter observations from NASA ASF DAAC.",
            "Thresholding segments surface water scattering divergence across multi-temporal baselines.",
            "Analysis confidence is calibrated against radar noise floors and valid pixel thresholds.",
            "Subject to satellite orbit pass schedule and local topographically induced radar shadow/layover.",
        ]
    if not analysis.quality.quality_gate_passed:
        limitations.append("Analysis failed data quality requirements; change mask thresholding is disabled.")
    if val_status_str == "unvalidated":
        limitations.append("This domain algorithm has not undergone formal independent ground-truth validation.")

    return LabDetailView(
        analysis_id=analysis.id,
        target_id=target_id,
        title=f"{domain_label} Analysis — {aoi_name}",
        aoi_id=analysis.aoi_id,
        aoi_name=aoi_name,
        aoi_country=aoi_country,
        aoi_region=aoi_region,
        domain_raw=analysis.domain.value,
        domain_label=domain_label,
        observation_state_raw=analysis.observation_state.value,
        observation_state_label=state_label,
        observation_state_badge_class=state_badge_class,
        classification_status_label="RESOLVED" if analysis.classification_status.value == "resolved" else "UNCLASSIFIED",
        product_maturity_label=maturity_val,
        product_maturity_badge_class=maturity_badge_class,
        validation_status_label=val_label,
        validation_status_badge_class=val_badge_class,
        manifest_id=analysis.manifest_id,
        is_synthetic=is_synthetic,
        synthetic_badge_text="DEMO LAB" if is_synthetic else "REAL NISAR ANALYSIS",
        synthetic_warning=("Synthetic evidence and analysis controls are used to demonstrate the scientist workflow. These are not NISAR measurements." if is_synthetic else ""),
        
        event_id=linked_event.id if linked_event else None,
        event_url=f"/event/{linked_event.id}" if linked_event else None,
        map_url=f"/map?aoi={analysis.aoi_id}",

        evidence=evidence,
        lab_metrics=lab_metrics,
        has_lab_metrics=lab_metrics is not None,
        active_channel=active_chan,
        available_channels=channels,
        channel_label=chan_label,
        has_multiple_channels=len(channels) > 1,

        has_histogram=has_hist,
        histogram=hist_data,

        has_threshold_preview=has_threshold,
        threshold_preview=thresh_preview,

        quality_gate_passed=analysis.quality.quality_gate_passed,
        quality_notes=analysis.quality.notes,
        valid_pixel_fraction_display=f"{analysis.quality.valid_pixel_fraction * 100:.1f}%",
        has_quality_mask=lab_metrics.has_quality_mask if lab_metrics else False,
        quality_mask_url=lab_metrics.quality_mask_url if lab_metrics else None,
        pixel_value_summary=lab_metrics.pixel_value_summary if lab_metrics else None,

        method_steps=method_steps,
        before_acquisition=before_detail,
        after_acquisition=after_detail,

        quality_parameters=qual_params,
        detection_parameters=det_params,
        pipeline_version=manifest.pipeline_version if manifest else "v1.0.0",
        code_version=manifest.code_version if manifest else "main",
        comparison_policy=manifest.comparison_policy if manifest else "Standard",
        threshold_selection_method=manifest.threshold_selection_method if manifest else "Configured",

        validation_status=val_status_str,
        independent_validation=val_indep,
        number_of_independent_events=val_num_indep,
        validation_statement=val_statement,
        reference_dataset=validation.reference_dataset if validation else None,
        metrics=val_metrics_list,

        limitations=limitations,
    )
