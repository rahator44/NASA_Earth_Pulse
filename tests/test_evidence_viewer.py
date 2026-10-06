"""
Test Suite for Step 8: Before / After Satellite Evidence Viewer.
Covers all required test cases:
1. evidence fixture files validate against Pydantic model.
2. GET /api/demo/analyses/{id}/evidence returns 200 for valid record.
3. missing analysis evidence returns 404.
4. Event Detail contains evidence viewer for analysis with evidence.
5. Image Lab contains evidence viewer.
6. synthetic evidence shows: "Synthetic visual fixture".
7. insufficient_data analysis does not show fake Difference or Change Mask products.
8. before and after acquisition labels render.
9. viewer mode buttons are present (Swipe, Before, After, Difference, Change Mask).
10. opacity control exists where overlay evidence exists.
11. all previous Step 1–7 tests remain passing.
"""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.evidence import AnalysisEvidence

client = TestClient(app)


def test_evidence_fixtures_validate_against_pydantic():
    """Test 1: evidence fixture files validate."""
    fixture_path = Path("app/static/data/demo/evidence.json")
    assert fixture_path.exists()
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert len(data) >= 4

    for item in data:
        ev = AnalysisEvidence.model_validate(item)
        assert ev.analysis_id
        assert ev.disclaimer


def test_get_analysis_evidence_api_200():
    """Test 2: GET /api/demo/analyses/{id}/evidence returns 200 for valid record."""
    response = client.get("/api/demo/analyses/analysis_synth_001/evidence")
    assert response.status_code == 200
    data = response.json()
    assert data["analysis_id"] == "analysis_synth_001"
    assert data["before"]["url"] == "/static/images/demo-evidence/synth_001_before.svg"
    assert data["after"]["url"] == "/static/images/demo-evidence/synth_001_after.svg"
    assert data["difference"]["url"] == "/static/images/demo-evidence/synth_001_diff.svg"
    assert data["change_mask"]["url"] == "/static/images/demo-evidence/synth_001_mask.svg"


def test_missing_analysis_evidence_returns_404():
    """Test 3: missing analysis evidence returns 404."""
    response = client.get("/api/demo/analyses/non_existent_analysis/evidence")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_event_detail_contains_evidence_viewer():
    """Test 4: Event Detail contains evidence viewer for analysis with evidence."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "SATELLITE EVIDENCE VIEWER" in response.text
    assert "initEvidenceViewer" in response.text
    assert "synth_001_before.svg" in response.text
    assert "synth_001_after.svg" in response.text


def test_image_lab_contains_evidence_viewer():
    """Test 5: Image Lab contains evidence viewer."""
    response = client.get("/lab/analysis_synth_001")
    assert response.status_code == 200
    assert "initEvidenceViewer" in response.text
    assert "synth_001_before.svg" in response.text
    assert "synth_001_after.svg" in response.text


def test_synthetic_evidence_shows_disclaimer_notice():
    """Test 6: synthetic evidence shows 'Synthetic visual fixture'."""
    res_event = client.get("/event/event_synth_001")
    assert res_event.status_code == 200
    assert "Synthetic visual fixture" in res_event.text
    assert "DEMO VISUAL" in res_event.text

    res_lab = client.get("/lab/analysis_synth_001")
    assert res_lab.status_code == 200
    assert "Synthetic visual fixture" in res_lab.text
    assert "DEMO VISUAL" in res_lab.text


def test_insufficient_data_withholds_fake_products():
    """Test 7: insufficient_data analysis does not show fake Difference or Change Mask products."""
    res_ev3 = client.get("/event/event_synth_003")
    assert res_ev3.status_code == 200
    assert "QUALITY GATE NOT PASSED" in res_ev3.text
    assert "Difference and change-mask products are unavailable because the analysis quality gate was not passed." in res_ev3.text
    # SVG for diff or mask must NOT be present
    assert "synth_003_diff.svg" not in res_ev3.text
    assert "synth_003_mask.svg" not in res_ev3.text

    # Also verify via API
    api_res = client.get("/api/demo/analyses/analysis_synth_003/evidence")
    assert api_res.status_code == 200
    data = api_res.json()
    assert data["quality_gate_passed"] is False
    assert data["after"] is None
    assert data["difference"] is None
    assert data["change_mask"] is None


def test_before_and_after_acquisition_labels_render():
    """Test 8: before and after acquisition labels render."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "BEFORE OBSERVATION" in response.text
    assert "AFTER OBSERVATION" in response.text
    assert "2026-08-01" in response.text
    assert "2026-08-13" in response.text


def test_viewer_mode_buttons_present():
    """Test 9: viewer mode buttons are present (Swipe, Before, After, Difference, Change Mask)."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "Swipe" in response.text
    assert "Before" in response.text
    assert "After" in response.text
    assert "Difference" in response.text
    assert "Change Mask" in response.text


def test_opacity_control_exists_for_overlay_modes():
    """Test 10: opacity control exists where overlay evidence exists."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "Opacity:" in response.text
    assert 'type="range"' in response.text
    assert "opacity" in response.text
