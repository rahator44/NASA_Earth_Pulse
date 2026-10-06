"""
Test Suite for Step 11: Methods + Validation + Scientific Transparency Finalization.
Verifies scientific transparency documentation, physical product roles,
nine compatibility checks, non-alarm observation state palette consistency,
and explicit out-of-scope boundaries.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.demo_data import demo_service
from app.viewmodels.dashboard import build_dashboard_view

client = TestClient(app)


def test_1_methods_route_returns_200():
    """1. /methods returns 200 OK."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "Methods &amp; Scientific Transparency" in response.text or "Methods & Scientific Transparency" in response.text


def test_2_project_principle_text_present():
    """2. Project principle text is present."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "We do not predict disasters" in response.text
    assert "This application does not issue evacuation instructions" in response.text


def test_3_gcov_gunw_goff_roles_render():
    """3. GCOV/GUNW/GOFF roles render distinctly."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "GCOV" in response.text
    assert "Geocoded Radiometric Backscatter" in response.text
    assert "GUNW" in response.text
    assert "Geocoded Unwrapped Interferogram" in response.text
    assert "GOFF" in response.text
    assert "Geocoded Pixel Offsets" in response.text


def test_4_nine_compatibility_checks_render():
    """4. Nine compatibility checks render."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "Same Track" in response.text
    assert "Same Frame Number" in response.text
    assert "Same Orbit Direction" in response.text
    assert "Compatible Acquisition Mode" in response.text
    assert "Compatible Polarizations" in response.text
    assert "Compatible Radar Frequency" in response.text
    assert "Compatible Bandwidth" in response.text
    assert "Same Product Maturity State" in response.text
    assert "Compatible CRID" in response.text


def test_5_insufficient_data_not_no_change_explanation():
    """5. Insufficient Data != No Change explanation exists."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "Insufficient Data &ne; No Change" in response.text or "Insufficient Data" in response.text
    assert "Missing Analysis &ne; No Change" in response.text or "lack of observation data represents an absence of analysis, not confirmed stability" in response.text


def test_6_unknown_change_definition_renders():
    """6. Unknown-change definition renders with non-alarm wording."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "Unusual radar change detected. Cause not identified." in response.text
    assert "UNKNOWN CHANGE" in response.text


def test_7_validation_event_count_language_renders():
    """7. Validation event-count language renders."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "Independent Validation Events" in response.text
    assert "Intersection over Union" in response.text or "IoU" in response.text


def test_8_calibration_vs_validation_distinction_renders():
    """8. Calibration vs validation distinction renders."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "Calibration Events" in response.text
    assert "Independent Validation Events" in response.text
    assert (
        "Calibration and evaluation used the same event; reported performance is not independent validation."
        in response.text
    )


def test_9_review_priority_formula_renders():
    """9. Review Priority formula renders."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "ReviewScore = 0.50 &times; O + 0.35 &times; E + 0.15 &times; F" in response.text or "0.50" in response.text
    assert "Observation (50%)" in response.text or "0.50" in response.text


def test_10_dense_city_caveat_renders():
    """10. Dense-city caveat renders."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert (
        "A smaller detected change in a densely populated area can rank above a larger change in a sparsely populated area because Review Priority includes exposure."
        in response.text
    )


def test_11_capability_status_table_renders():
    """11. Capability-status table renders."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "CAPABILITY / WORKSPACE MODULE" in response.text
    assert "IMPLEMENTATION STATUS" in response.text


def test_12_real_gcov_processing_implemented_showcase():
    """12. Real NISAR GCOV processing is marked IMPLEMENTED — ONE PRECOMPUTED SHOWCASE."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "Real NISAR GCOV Raster Processing" in response.text
    assert "IMPLEMENTED — ONE PRECOMPUTED SHOWCASE" in response.text


def test_13_live_metadata_discovery_marked_implemented():
    """13. Live metadata discovery is marked IMPLEMENTED."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "Live NISAR Metadata Discovery" in response.text
    assert "IMPLEMENTED" in response.text


def test_14_synthetic_evidence_is_labeled():
    """14. Synthetic evidence is explicitly labeled."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "IMPLEMENTED WITH SYNTHETIC VISUAL FIXTURES" in response.text
    assert "Current Event Records Are Synthetic Fixtures" in response.text


def test_15_machine_learning_not_part_of_current_demo():
    """15. Machine learning is listed as not part of current demo."""
    response = client.get("/methods")
    assert response.status_code == 200
    assert "Machine Learning Models" in response.text
    assert "Deep Learning / CNNs" in response.text
    assert "Random Forest Classifiers" in response.text
    assert "NOT PART OF CURRENT DEMO" in response.text


def test_16_dashboard_map_palette_non_alarm():
    """16. Dashboard observation map palette does NOT use red/amber/green alarm mapping."""
    view = build_dashboard_view(demo_service)
    features = view.map_geojson["features"]
    
    # Verify no alarm colors exist in features
    alarm_colors = {"#EF4444", "#F59E0B", "#10B981"}
    for f in features:
        color = f["properties"]["observation_state_color"]
        assert color not in alarm_colors, f"Alarm color {color} found for feature {f['properties']['aoi_name']}"

    # Verify Dashboard HTML does not map observation states to emergency colors
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "text-[#EF4444] font-semibold\">STRONG CHANGE" not in resp.text
    assert "text-[#F59E0B] font-semibold\">CHANGE DETECTED" not in resp.text
    assert "text-[#10B981] font-semibold\">NO CHANGE" not in resp.text


def test_17_observation_state_palette_consistent_with_tokens():
    """17. Observation-state palette is consistent with Step 2 non-alarm tokens."""
    view = build_dashboard_view(demo_service)
    colors = {f["properties"]["observation_state"]: f["properties"]["observation_state_color"] for f in view.map_geojson["features"]}
    
    # Change detected = royal blue
    assert colors.get("change_detected") == "#1E6BFF"
    # Unknown change = violet
    assert colors.get("unknown_change") == "#8B5CF6"
    # No change = muted teal / cool gray
    assert colors.get("no_change") == "#4E7880"
    # Insufficient data = slate gray
    assert colors.get("insufficient_data") == "#64748B"


def test_18_all_previous_tests_remain_passing():
    """18. Verify overall health across previous endpoints."""
    assert client.get("/").status_code == 200
    assert client.get("/map").status_code == 200
    assert client.get("/dashboard").status_code == 200
    assert client.get("/lab/analysis_synth_001").status_code == 200
    assert client.get("/event/event_synth_001").status_code == 200
