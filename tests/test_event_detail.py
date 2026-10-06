"""
Test Suite for Step 7: Data-Driven Event Detail + Evidence + Provenance.
Covers all 19 required test cases:
1. valid event route returns 200.
2. invalid event ID returns 404.
3. event title renders from fixture data.
4. observation state renders correctly.
5. domain and observation state are displayed separately.
6. synthetic event shows DEMO FIXTURE warning.
7. unknown event shows: "Cause not identified."
8. ambiguous region renders multiple candidate interpretations.
9. insufficient_data does not display a fake change metric.
10. no_change is distinct from insufficient_data.
11. acquisition comparison renders stored before/after IDs.
12. manifest ID renders.
13. exposure is in a separate EXPOSURE CONTEXT section.
14. validation status renders accurately.
15. unvalidated event does not claim confidence.
16. /lab/{analysis_id} link is correct.
17. /map?aoi={aoi_id} link is correct.
18. /copilot?event={event_id} link is correct.
19. existing Step 1–6 tests remain passing.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_valid_event_route_returns_200():
    """Test 1: valid event route returns 200."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_invalid_event_id_returns_404():
    """Test 2: invalid event ID returns 404 with styled page."""
    response = client.get("/event/does-not-exist")
    assert response.status_code == 404
    assert "OBSERVATION NOT FOUND" in response.text
    assert "The requested analysis record" in response.text
    assert "Return to Change Feed" in response.text
    assert "Explore Map" in response.text


def test_event_title_renders_from_fixture():
    """Test 3: event title renders from fixture data."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "Synthetic Wetland Fluctuation Event" in response.text


def test_observation_state_renders_correctly():
    """Test 4: observation state renders correctly."""
    res1 = client.get("/event/event_synth_001")
    assert "CHANGE DETECTED" in res1.text

    res2 = client.get("/event/event_synth_002")
    assert "UNKNOWN CHANGE" in res2.text

    res3 = client.get("/event/event_synth_003")
    assert "INSUFFICIENT DATA" in res3.text

    res4 = client.get("/event/event_synth_004")
    assert "NO CHANGE" in res4.text


def test_domain_and_observation_state_are_displayed_separately():
    """Test 5: domain and observation state are displayed separately."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    # Both distinct label containers are present
    assert "OBSERVATION" in response.text
    assert "CHANGE DETECTED" in response.text
    assert "INTERPRETATION" in response.text
    assert "Flood / Wetland" in response.text


def test_synthetic_event_shows_demo_fixture_warning():
    """Test 6: synthetic event shows DEMO FIXTURE warning."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "DEMO FIXTURE" in response.text
    assert "Synthetic development fixture — not an Earth observation result." in response.text


def test_unknown_event_shows_cause_not_identified():
    """Test 7: unknown event shows 'Cause not identified.'"""
    response = client.get("/event/event_synth_002")
    assert response.status_code == 200
    assert "Unusual radar change detected. Cause not identified." in response.text
    assert "CAUSE NOT CONFIRMED" in response.text


def test_ambiguous_region_renders_multiple_candidate_interpretations():
    """Test 8: ambiguous region renders multiple candidate interpretations."""
    response = client.get("/event/event_synth_002")
    assert response.status_code == 200
    assert "POSSIBLE INTERPRETATIONS" in response.text
    assert "Flood / Wetland" in response.text
    assert "Vegetation Disturbance" in response.text
    assert "Evidence Score:" in response.text
    assert "This is a rule/evidence score, not a probability of cause." in response.text
    # Fire corroboration
    assert "FIRMS ACTIVE FIRE CORROBORATION" in response.text


def test_insufficient_data_does_not_display_fake_change_metric():
    """Test 9: insufficient_data does not display a fake change metric."""
    response = client.get("/event/event_synth_003")
    assert response.status_code == 200
    assert "INSUFFICIENT DATA" in response.text
    assert "Not enough usable data was available to determine surface change." in response.text
    assert "Primary measurements withheld." in response.text
    assert "QUANTIFIED METRIC(S)" not in response.text
    assert "QUALITY GATE NOT PASSED" in response.text
    assert "Valid-pixel fraction below configured minimum." in response.text


def test_no_change_is_distinct_from_insufficient_data():
    """Test 10: no_change is distinct from insufficient_data."""
    res_no_change = client.get("/event/event_synth_004")
    assert res_no_change.status_code == 200
    assert "NO CHANGE" in res_no_change.text
    assert "INSUFFICIENT DATA" not in res_no_change.text
    assert "Max Relative Displacement" in res_no_change.text
    assert "1.80 mm" in res_no_change.text
    assert "GATE PASSED" in res_no_change.text


def test_acquisition_comparison_renders_stored_before_after_ids():
    """Test 11: acquisition comparison renders stored before/after IDs."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "SYNTH_GCOV_A_001" in response.text
    assert "SYNTH_GCOV_A_002" in response.text
    assert "BEFORE OBSERVATION" in response.text
    assert "AFTER OBSERVATION" in response.text


def test_manifest_id_renders():
    """Test 12: manifest ID renders."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "manifest_synth_001" in response.text
    assert "PIPELINE MANIFEST:" in response.text


def test_exposure_in_separate_exposure_context_section():
    """Test 13: exposure is in a separate EXPOSURE CONTEXT section."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "EXPOSURE CONTEXT" in response.text
    assert "SEVERITY" not in response.text
    assert "RISK LEVEL" not in response.text
    assert "Estimated Population" in response.text
    assert "1,250" in response.text


def test_validation_status_renders_accurately():
    """Test 14: validation status renders accurately."""
    res1 = client.get("/event/event_synth_001")
    assert "Validated on 2 independent event(s)." in res1.text
    assert "Intersection over Union (IoU)" in res1.text
    assert "0.84" in res1.text

    res4 = client.get("/event/event_synth_004")
    assert "Threshold calibrated on available event data; no independent validation." in res4.text
    assert "Displacement RMSE" in res4.text


def test_unvalidated_event_does_not_claim_confidence():
    """Test 15: unvalidated event does not claim confidence."""
    response = client.get("/event/event_synth_002")
    assert response.status_code == 200
    assert "Unvalidated." in response.text
    assert "92% confidence" not in response.text
    assert "high confidence" not in response.text


def test_lab_analysis_link_is_correct():
    """Test 16: /lab/{analysis_id} link is correct."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "/lab/analysis_synth_001" in response.text


def test_map_aoi_link_is_correct():
    """Test 17: /map?aoi={aoi_id} link is correct."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "/map?aoi=aoi_synth_alpha" in response.text


def test_copilot_event_link_is_correct():
    """Test 18: /copilot?event={event_id} link is correct."""
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "/copilot?event=event_synth_001" in response.text
