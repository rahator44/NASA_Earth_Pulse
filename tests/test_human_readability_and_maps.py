"""High-value regression tests for human explanations and consistent maps."""
from fastapi.testclient import TestClient

from app.main import app
from app.services.demo_data import demo_service
from app.viewmodels.dashboard import build_dashboard_view

client = TestClient(app)


def test_coverage_panel_is_public_first_and_scientist_details_are_secondary():
    js = client.get("/static/js/area_inspector.js").text
    assert "NISAR DATA FOR THIS AREA" in js
    assert "Radar Surface Backscatter" in js
    assert "Ground Movement Evidence" in js
    assert "Surface / Glacier Motion Evidence" in js
    assert "Coverage alone does not mean that a change occurred" in js
    assert "SCIENTIST METADATA · ALL ACQUISITIONS & PAIR CHECKS" in js


def test_area_inspector_explains_nisar_product_codes_in_public_language():
    js = client.get("/static/js/area_inspector.js").text
    assert "HOW TO READ THE NISAR DATA" in js
    assert "product_name_public" in js
    assert "orbit_direction_public" in js
    assert "maturity_label" in js
    assert "polarization_explanations" in js


def test_shared_basemap_keeps_osm_under_optional_satellite():
    js = client.get("/static/js/map_basemaps.js").text
    assert "Keep OSM visible underneath satellite" in js
    assert "map.setLayoutProperty(OSM_LAYER_ID, 'visibility', 'visible')" in js
    assert "api\\.mapbox\\.com|mapbox-satellite" in js


def test_dashboard_map_has_attribution_scale_and_correct_per_feature_explanation():
    js = client.get("/static/js/dashboard_map.js").text
    assert "AttributionControl" in js
    assert "ScaleControl" in js
    view = build_dashboard_view(demo_service)
    by_id = {f["properties"]["analysis_id"]: f["properties"] for f in view.map_geojson["features"]}
    assert by_id["real_flood_001"]["human_headline"] == "Surface-water change detected"
    assert by_id["analysis_synth_002"]["human_headline"] == "Unusual radar change detected. Cause not identified."


def test_dashboard_surface_change_overview_includes_real_showcase_without_fake_exposure():
    view = build_dashboard_view(demo_service)
    real = next(item for item in view.surface_changes if item["analysis_id"] == "real_flood_001")
    assert real["is_real"] is True
    assert real["human_label"] == "REAL NISAR ANALYSIS"
    assert "surface-water" in real["headline"].lower()
    html = client.get("/dashboard").text
    assert "SURFACE CHANGE OVERVIEW" in html
    assert "These are observations and interpretations, not danger ratings" in html


def test_event_mini_map_uses_non_alarm_observation_palette():
    from pathlib import Path
    template = (Path(__file__).parents[1] / "app/templates/pages/event_detail.html").read_text()
    for color in ("#1E6BFF", "#00D2FF", "#8B5CF6", "#4E7880", "#64748B"):
        assert color in template
    assert 'const stateColor' in template
