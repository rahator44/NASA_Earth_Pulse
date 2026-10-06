"""Regression tests for explanation-first scientific wording and map geometry."""
import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.services.demo_data import demo_service
from app.services.sar_science import mask_to_geojson_polygons
from app.viewmodels.dashboard import build_dashboard_view


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_water_uses_canonical_signed_difference_and_expansion_direction():
    analysis = demo_service.get_analysis("analysis_synth_001")
    assert "mean_backscatter_difference_db" in analysis.measurements
    assert "backscatter_reduction_mean_db" not in analysis.measurements
    assert analysis.measurements["mean_backscatter_difference_db"] == -3.8
    situation = demo_service.get_situation_for_analysis("analysis_synth_001")
    assert situation.interpretations[0].code == "surface_water_expansion"
    assert "recession" not in situation.interpretations[0].public_label.lower()


def test_real_showcase_explains_candidate_vs_retained_area():
    analysis = demo_service.get_analysis("real_flood_001")
    m = analysis.measurements
    assert m["candidate_radar_change_area_km2"] == 0.837
    assert m["retained_mapped_region_area_km2"] == 0.527
    assert m["removed_small_component_area_km2"] == 0.31
    situation = demo_service.get_situation_for_analysis("real_flood_001")
    assert "Candidate radar-change pixels: 0.837 km²" in situation.what_changed
    assert "0.527 km² remained as mapped regions" in situation.what_changed
    assert "0.310 km²" in situation.what_changed
    assert situation.interpretations[0].rule_id == "GCOV_BACKSCATTER_DECREASE_01"
    assert situation.interpretations[0].public_reason
    assert situation.interpretations[0].alternative_explanations


def test_dswx_is_context_not_independent_support_for_real_showcase():
    situation = demo_service.get_situation_for_analysis("real_flood_001")
    assert not situation.supporting_evidence
    dswx = [item for item in situation.context if "dswx" in item.measurement_name.lower()]
    assert dswx
    assert dswx[0].support_level == "contextual"
    assert "has not spatially compared" in dswx[0].description_public
    assert all("corroboration" not in item.measurement_name.lower() for item in situation.context)


def test_current_manifest_states_reference_is_not_spatially_validated():
    manifest = json.loads((ROOT / "data/real/flood_showcase/processed/manifest_real_flood_001.json").read_text())
    assert manifest["results"]["reference_spatial_comparison_performed"] is False
    assert manifest["results"]["metrics_source"] == "not_independently_validated"


def test_polygonizer_uses_actual_component_outline_and_neutral_properties():
    # L-shaped component: a bounding box would have only 5 ring coordinates.
    mask = np.zeros((6, 6), dtype=bool)
    mask[1:5, 1] = True
    mask[4, 1:5] = True
    fc = mask_to_geojson_polygons(mask, (-91.5, 30.0, -91.0, 30.5), min_pixels=2)
    assert len(fc["features"]) == 1
    feature = fc["features"][0]
    assert len(feature["geometry"]["coordinates"][0]) > 5
    assert "confidence" not in feature["properties"]
    assert "observation_state" not in feature["properties"]


def test_stored_real_polygons_are_true_outlines_not_rectangles():
    geo = json.loads((ROOT / "data/real/flood_showcase/processed/water_change_polygons.geojson").read_text())
    assert geo["metadata"]["geometry_method"].startswith("true raster component outlines")
    assert any(len(feature["geometry"]["coordinates"][0]) > 5 for feature in geo["features"])


def test_dashboard_uses_situation_interpretations_instead_of_hardcoded_hazards():
    view = build_dashboard_view(demo_service)
    unknown = next(item for item in view.review_queue if item.analysis_id == "analysis_synth_002")
    situation = demo_service.get_situation_for_analysis("analysis_synth_002")
    expected = [f"{item.public_label} — {item.status.replace('_', ' ')}" for item in situation.interpretations[1:]]
    assert unknown.candidate_interpretations == expected
    assert "Surface inundation or soil moisture spike" not in unknown.candidate_interpretations
    assert "Wildfire vegetation canopy disturbance" not in unknown.candidate_interpretations


def test_public_event_explains_why_and_keeps_rule_id_scientist_only():
    response = client.get("/event/real_flood_001")
    assert response.status_code == 200
    assert "WHY THIS INTERPRETATION?" in response.text
    assert "OTHER POSSIBLE EXPLANATIONS" in response.text
    assert "GCOV_BACKSCATTER_DECREASE_01" in response.text
    assert "Candidate Radar-Change Pixels" in response.text


def test_maps_have_nonblank_failure_messages():
    dashboard_js = (ROOT / "app/static/js/dashboard_map.js").read_text()
    event_template = (ROOT / "app/templates/pages/event_detail.html").read_text()
    assert "Interactive map could not load." in dashboard_js
    assert "Interactive map could not load." in event_template
