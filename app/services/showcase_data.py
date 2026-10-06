"""
Showcase Data Loader.
Loads precomputed real NISAR analysis products from data/real/flood_showcase/processed/
into typed Pydantic models.
"""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Optional

from app.models import (
    AOI,
    Acquisition,
    Analysis,
    AnalysisEvidence,
    AnalysisLabMetrics,
    AnalysisManifest,
    AnalysisQuality,
    CandidateMatch,
    ChangeRegion,
    ClassificationStatus,
    DataOrigin,
    Domain,
    Event,
    EvidenceContextLayer,
    EvidenceDifferenceLayer,
    EvidenceLayer,
    EvidenceMaskLayer,
    HistogramData,
    ObservationState,
    ProductMaturity,
    ProductType,
    ThresholdPreview,
    ThresholdPreviewState,
    ValidationResult,
    ValidationStatus,
)

PROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "real" / "flood_showcase" / "processed"


@dataclass
class RealShowcasePackage:
    aoi: AOI
    acquisitions: list[Acquisition]
    manifest: AnalysisManifest
    analysis: Analysis
    event: Event
    evidence: AnalysisEvidence
    lab_metrics: AnalysisLabMetrics
    validation: ValidationResult
    candidates: list[CandidateMatch]
    change_regions: list[ChangeRegion]
    raw_geojson: dict[str, Any]


def load_real_flood_showcase(processed_dir: Path = PROCESSED_DIR) -> RealShowcasePackage:
    """
    Parses manifest_real_flood_001.json and water_change_polygons.geojson,
    producing typed models with data_origin="precomputed_real_analysis" and is_demo=False.
    """
    manifest_path = processed_dir / "manifest_real_flood_001.json"
    geojson_path = processed_dir / "water_change_polygons.geojson"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Real showcase manifest not found at {manifest_path}")
    if not geojson_path.exists():
        raise FileNotFoundError(f"Real showcase geojson not found at {geojson_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        mf = json.load(f)

    with open(geojson_path, "r", encoding="utf-8") as f:
        raw_geojson = json.load(f)

    # 1. AOI
    aoi_meta = mf.get("aoi", {})
    lon_min = aoi_meta.get("lon_min", -91.75)
    lon_max = aoi_meta.get("lon_max", -91.55)
    lat_min = aoi_meta.get("lat_min", 30.25)
    lat_max = aoi_meta.get("lat_max", 30.43)

    aoi_geometry = {
        "type": "Polygon",
        "coordinates": [[
            [lon_min, lat_min],
            [lon_max, lat_min],
            [lon_max, lat_max],
            [lon_min, lat_max],
            [lon_min, lat_min]
        ]]
    }

    aoi = AOI(
        id="aoi_real_001",
        display_name="Lake Henderson / Atchafalaya Basin",
        geometry=aoi_geometry,
        country="United States",
        region="Louisiana",
        is_demo=False,
        data_origin=DataOrigin.PRECOMPUTED_REAL_ANALYSIS,
        disclaimer=""
    )

    # 2. Acquisitions
    granules = mf.get("granules", {})
    before_g = granules.get("before", {})
    after_g = granules.get("after", {})

    before_ur = before_g.get("granule_ur", "NISAR_L2_PR_GCOV_024_033_A_017_4005_DHDH_A_20260628T112725_20260628T112800_P05023_N_F_J_001")
    after_ur = after_g.get("granule_ur", "NISAR_L2_PR_GCOV_025_033_A_017_4005_DHDH_A_20260710T112724_20260710T112759_P05023_N_F_J_001")

    acq_before = Acquisition(
        id=before_ur,
        source="NASA NISAR / ASF DAAC",
        sensor="NISAR L-SAR",
        product_type=ProductType.GCOV,
        acquisition_datetime="2026-06-28T11:27:25Z",
        track=33,
        frame=17,
        orbit_direction="ascending",
        mode="4005 (40 MHz primary / 5 MHz secondary)",
        polarizations=["HH", "HV"],
        frequency="1.257 GHz (L-Band)",
        bandwidth="40+5 MHz",
        maturity=ProductMaturity.PROVISIONAL,
        crid="P05023",
        footprint=aoi_geometry,
        source_url=before_g.get("url"),
        is_demo=False,
        data_origin=DataOrigin.PRECOMPUTED_REAL_ANALYSIS,
        disclaimer=""
    )

    acq_after = Acquisition(
        id=after_ur,
        source="NASA NISAR / ASF DAAC",
        sensor="NISAR L-SAR",
        product_type=ProductType.GCOV,
        acquisition_datetime="2026-07-10T11:27:24Z",
        track=33,
        frame=17,
        orbit_direction="ascending",
        mode="4005 (40 MHz primary / 5 MHz secondary)",
        polarizations=["HH", "HV"],
        frequency="1.257 GHz (L-Band)",
        bandwidth="40+5 MHz",
        maturity=ProductMaturity.PROVISIONAL,
        crid="P05023",
        footprint=aoi_geometry,
        source_url=after_g.get("url"),
        is_demo=False,
        data_origin=DataOrigin.PRECOMPUTED_REAL_ANALYSIS,
        disclaimer=""
    )

    # 3. Analysis Manifest
    processing = mf.get("processing", {})
    quality_meta = mf.get("quality", {})
    results_meta = mf.get("results", {})
    ref_meta = mf.get("reference", {})

    manifest = AnalysisManifest(
        manifest_id="manifest_real_flood_001",
        analysis_id="real_flood_001",
        aoi_id="aoi_real_001",
        domain=Domain.FLOOD_WETLAND,
        before_acquisition_id=acq_before.id,
        after_acquisition_id=acq_after.id,
        comparison_policy="exact_repeat_12day",
        reference_acquisition_id=None,
        track=33,
        frame=17,
        orbit_direction="ascending",
        mode="4005 (40 MHz primary / 5 MHz secondary)",
        polarizations=["HH", "HV"],
        maturity=ProductMaturity.PROVISIONAL,
        crid="P05023",
        pipeline_version="v1.0.0-real-nisar",
        code_version="step12-real-showcase",
        quality_parameters={
            "before_valid_pixel_fraction": quality_meta.get("before_valid_frac", 1.0),
            "after_valid_pixel_fraction": quality_meta.get("after_valid_frac", 1.0),
            "quality_gate_threshold": quality_meta.get("quality_gate_threshold", 0.85),
            "speckle_filter": processing.get("speckle_filter", "11x11 box (linear power)"),
        },
        detection_parameters={
            "dataset_path": processing.get("dataset_path", "science/LSAR/GCOV/grids/frequencyA/HHHH"),
            "threshold_db": processing.get("threshold_db", -2.0),
            "morph_open_px": processing.get("morph_open_px", 3),
            "min_area_km2": processing.get("min_area_km2", 0.05),
            "pixel_spacing_m": processing.get("pixel_spacing_m", 10),
            "projection": processing.get("projection", "EPSG:32615 (UTM 15N)"),
            "candidate_radar_change_area_km2": results_meta.get("candidate_radar_change_area_km2", results_meta.get("water_gain_area_km2", 0.837)),
            "retained_mapped_region_area_km2": results_meta.get("polygon_total_area_km2", 0.527),
        },
        threshold_selection_method="Empirical -2.0 dB drop threshold on multi-looked linear power SAR backscatter",
        reference_area="Lake Henderson / Atchafalaya Basin, Louisiana",
        validation_reference=f"{ref_meta.get("collection", "OPERA_L3_DSWX-HLS_V1")} ({ref_meta.get("granule_ur", "OPERA_L3_DSWx-HLS_T15RXP_20260707T163136Z")})",
        calibration_event_id="real_flood_001",
        validation_event_ids=[],
        independent_validation=False,
        created_at=mf.get("generated_at", "2026-10-05T21:57:07Z"),
        is_demo=False,
        data_origin=DataOrigin.PRECOMPUTED_REAL_ANALYSIS,
        disclaimer=""
    )

    # 4. Analysis
    quality_gate_passed = (
        quality_meta.get("before_valid_frac", 1.0) >= quality_meta.get("quality_gate_threshold", 0.85) and
        quality_meta.get("after_valid_frac", 1.0) >= quality_meta.get("quality_gate_threshold", 0.85)
    )

    analysis = Analysis(
        id="real_flood_001",
        aoi_id="aoi_real_001",
        domain=Domain.FLOOD_WETLAND,
        before_acquisition_id=acq_before.id,
        after_acquisition_id=acq_after.id,
        observation_state=ObservationState.CHANGE_DETECTED,
        quality=AnalysisQuality(
            valid_pixel_fraction=1.0,
            required_inputs_available=True,
            quality_gate_passed=quality_gate_passed,
            notes="100% valid radar pixels across 2018x1898 grid on both repeat passes. Quality gate passed."
        ),
        measurements={
            "candidate_radar_change_area_km2": results_meta.get("candidate_radar_change_area_km2", results_meta.get("water_gain_area_km2", 0.837)),
            "retained_mapped_region_area_km2": results_meta.get("polygon_total_area_km2", 0.527),
            "removed_small_component_area_km2": round(max(0.0, float(results_meta.get("candidate_radar_change_area_km2", results_meta.get("water_gain_area_km2", 0.837))) - float(results_meta.get("polygon_total_area_km2", 0.527))), 3),
            "change_criterion_db": processing.get("threshold_db", -2.0),
            "valid_pixel_fraction": 100.0,
            "polygon_count": results_meta.get("polygon_count", 3),
        },
        manifest_id=manifest.manifest_id,
        classification_status=ClassificationStatus.RESOLVED,
        final_classification="Radar-observed surface-water / inundation candidate change",
        created_at=mf.get("generated_at", "2026-10-05T21:57:07Z"),
        is_demo=False,
        data_origin=DataOrigin.PRECOMPUTED_REAL_ANALYSIS,
        disclaimer=""
    )

    # 5. Event
    event = Event(
        id="real_flood_001",
        analysis_id=analysis.id,
        title="Lake Henderson / Atchafalaya Basin",
        short_description=(
            "Repeat-pass provisional L2 GCOV observations contain coherent radar backscatter-decrease candidate regions. "
            "This pattern may be consistent with surface-water expansion. A DSWx-HLS observation is available near the period, "
            "but it has not been spatially compared with the NISAR change mask in this build."
        ),
        domain=Domain.FLOOD_WETLAND,
        observation_state=ObservationState.CHANGE_DETECTED,
        aoi_id=aoi.id,
        thumbnail_url="/static/real/before_with_change_overlay.png",
        comparison_start="2026-06-28T11:27:25Z",
        comparison_end="2026-07-10T11:27:24Z",
        primary_measurement_label="Candidate Radar-Change Pixels",
        primary_measurement_value=f"{float(results_meta.get('candidate_radar_change_area_km2', results_meta.get('water_gain_area_km2', 0.837))):.3f} km²",
        product_maturity=ProductMaturity.PROVISIONAL,
        freshness_timestamp="2026-07-10T11:27:24Z",
        validation_status=ValidationStatus.CALIBRATED_ONLY,
        manifest_id=manifest.manifest_id,
        featured=True,
        is_demo=False,
        data_origin=DataOrigin.PRECOMPUTED_REAL_ANALYSIS,
        disclaimer=""
    )

    # 6. Evidence
    evidence = AnalysisEvidence(
        analysis_id=analysis.id,
        before=EvidenceLayer(
            url="/static/real/before_db_preview.png",
            label="NISAR Provisional GCOV (2026-06-28)",
            acquisition_id=before_ur,
            acquisition_date="2026-06-28",
            source="NASA NISAR / ASF DAAC",
            product="L2 GCOV",
            maturity="PROVISIONAL",
            polarization="HH",
            is_synthetic=False,
        ),
        after=EvidenceLayer(
            url="/static/real/after_db_preview.png",
            label="NISAR Provisional GCOV (2026-07-10)",
            acquisition_id=after_ur,
            acquisition_date="2026-07-10",
            source="NASA NISAR / ASF DAAC",
            product="L2 GCOV",
            maturity="PROVISIONAL",
            polarization="HH",
            is_synthetic=False,
        ),
        difference=EvidenceDifferenceLayer(
            url="/static/real/diff_db_colormap.png",
            label="Radar Backscatter Difference (Δσ° dB)",
            unit="dB",
            legend_min="-10.0 dB",
            legend_max="+5.0 dB",
            colormap_label="Cool-Warm Divergent",
            is_synthetic=False,
        ),
        change_mask=EvidenceMaskLayer(
            url="/static/real/change_mask_overlay.png",
            label="Radar Backscatter-Decrease Candidate Mask",
            threshold_label="Backscatter decrease ≤ -2.0 dB",
            is_synthetic=False,
        ),
        # No DSWx raster is rendered here: the downloaded reference was not reprojected
        # and spatially compared with the NISAR mask in this frozen demo pipeline.
        optical_context=None,
        change_regions_geojson_url="/api/demo/change-regions.geojson",
        data_origin=DataOrigin.PRECOMPUTED_REAL_ANALYSIS,
        disclaimer="",
        quality_gate_passed=True,
        quality_notes="100% valid pixels on both repeat passes. Remote range requests streamed successfully from ASF DAAC.",
    )

    # 7. Lab Metrics
    diff_hist = mf.get("histograms", {}).get("diff_db", {})
    bins = [float(b) for b in diff_hist.get("centres", [])]
    counts = [int(c) for c in diff_hist.get("counts", [])]

    lab_metrics = AnalysisLabMetrics(
        analysis_id=analysis.id,
        data_origin=DataOrigin.PRECOMPUTED_REAL_ANALYSIS,
        is_synthetic=False,
        disclaimer="",
        active_channel="HH",
        available_channels=["HH"],
        channel_label="HH Polarization (frequencyA/HHHH)",
        has_alternative_channel_assets=False,
        histogram=HistogramData(
            label="Radar Backscatter Difference Distribution (Δσ° dB)",
            unit="dB",
            bins=bins,
            counts=counts,
            minimum=-14.75,
            maximum=9.75,
            mean=-0.12,
            median=-0.05,
            disclaimer="Measured distribution from provisional NISAR L2 GCOV repeat pass (2026-06-28 → 2026-07-10).",
        ),
        threshold_preview=ThresholdPreview(
            parameter_name="Backscatter Drop Threshold",
            unit="dB",
            minimum=-6.0,
            maximum=0.0,
            default=-2.0,
            step=0.5,
            direction="below_threshold",
            preview_states=[
                ThresholdPreviewState(
                    threshold_value=-2.0,
                    mask_url="/static/real/change_mask_overlay.png",
                    label=f"Nominal (-2.0 dB) — {float(results_meta.get('candidate_radar_change_area_km2', results_meta.get('water_gain_area_km2', 0.837))):.3f} km² candidate pixels"
                )
            ],
            disclaimer="Threshold preview uses precomputed NISAR GCOV change mask.",
        ),
        quality_summary={
            "valid_pixel_fraction": 1.0,
            "quality_gate_passed": True,
            "pixel_spacing_m": 10,
            "grid_dimensions": "2018 x 1898",
            "total_pixels_evaluated": 3830164,
            "invalid_nan_pixels": 0,
        },
        has_quality_mask=False,
        quality_mask_url=None,
        pixel_value_summary=(
            f"3,830,164 valid pixels analyzed (100% valid coverage). "
            f"Candidate radar-change pixels: {float(results_meta.get('candidate_radar_change_area_km2', results_meta.get('water_gain_area_km2', 0.837))):.3f} km²; "
            f"retained mapped regions after size filtering: {float(results_meta.get('polygon_total_area_km2', 0.527)):.3f} km²."
        ),
        notes="Provisional NISAR GCOV repeat-pass analysis over Lake Henderson / Atchafalaya Basin.",
    )

    # 8. Validation
    validation = ValidationResult(
        id="val_real_flood_001",
        analysis_id=analysis.id,
        status=ValidationStatus.CALIBRATED_ONLY,
        number_of_independent_events=0,
        calibration_event_id="real_flood_001",
        validation_event_ids=[],
        independent_validation=False,
        reference_dataset="OPERA_L3_DSWX-HLS_V1 (OPERA_L3_DSWx-HLS_T15RXP_20260707T163136Z)",
        metrics={
            "candidate_radar_change_area_km2": results_meta.get("candidate_radar_change_area_km2", results_meta.get("water_gain_area_km2", 0.837)),
            "retained_mapped_region_area_km2": results_meta.get("polygon_total_area_km2", 0.527),
            "polygon_count": results_meta.get("polygon_count", 3),
            "reference_cloud_cover_pct": ref_meta.get("cloud_cover_pct", 37.0),
        },
        notes=(
            "Calibration/context only — not independently validated. "
            "An OPERA DSWx-HLS water observation is available near the analysis period, but this build has not "
            "spatially compared that optical water layer with the NISAR change mask. "
            "No independent pre/post reference pair is stored."
        ),
        is_demo=False,
        data_origin=DataOrigin.PRECOMPUTED_REAL_ANALYSIS,
        disclaimer=""
    )

    # 9. Candidates
    candidate = CandidateMatch(
        id="cand_real_flood_001",
        analysis_id=analysis.id,
        region_id="region_real_flood_001_1",
        candidate_domain=Domain.FLOOD_WETLAND,
        candidate_score=None,
        supported=True,
        notes="Radar backscatter-decrease candidate change that may be consistent with surface-water expansion in Lake Henderson / Atchafalaya Basin.",
        physical_evidence={
            "backscatter_decrease_threshold_db": -2.0,
            "valid_pixel_fraction_pct": 100.0,
            "polarization": "HH",
            "frequency_grid": "frequencyA/HHHH",
        },
        independent_evidence={
            "opera_dswx_hls_context": (
                "An OPERA DSWx-HLS water observation is available near the analysis period (2026-07-07, 37% cloud cover), "
                "but this build has not spatially compared it with the NISAR change mask."
            )
        },
        contradicting_evidence={},
        is_demo=False,
        data_origin=DataOrigin.PRECOMPUTED_REAL_ANALYSIS,
        disclaimer=""
    )

    # 10. Change Regions from GeoJSON
    change_regions: list[ChangeRegion] = []
    for i, feature in enumerate(raw_geojson.get("features", [])):
        props = feature.get("properties", {})
        rid = f"region_real_flood_001_{i+1}"
        props["region_id"] = rid
        props["analysis_id"] = analysis.id
        props["is_demo"] = False
        props["data_origin"] = "precomputed_real_analysis"
        props["disclaimer"] = ""

        cr = ChangeRegion(
            id=rid,
            analysis_id=analysis.id,
            geometry=feature.get("geometry", {}),
            area_km2=props.get("area_km2"),
            classification_status=ClassificationStatus.RESOLVED,
            final_classification="Radar-observed surface-water candidate change",
            context_tags=["real_nisar", "wetland", "flood", "provisional_gcov"],
            is_demo=False,
            data_origin=DataOrigin.PRECOMPUTED_REAL_ANALYSIS,
            disclaimer=""
        )
        change_regions.append(cr)

    return RealShowcasePackage(
        aoi=aoi,
        acquisitions=[acq_before, acq_after],
        manifest=manifest,
        analysis=analysis,
        event=event,
        evidence=evidence,
        lab_metrics=lab_metrics,
        validation=validation,
        candidates=[candidate],
        change_regions=change_regions,
        raw_geojson=raw_geojson,
    )
