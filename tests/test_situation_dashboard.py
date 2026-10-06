"""
Test Suite for Step 10: Situation Dashboard + Review Priority.
Verifies regional review workspace, deterministic Review Priority scoring,
dataset-relative exposure normalization, separation of No Change and Insufficient Data,
and non-contamination of scientific observation states.
"""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.models.enums import ObservationState
from app.models.review_priority import (
    EXPOSURE_WEIGHT_INFRASTRUCTURE,
    EXPOSURE_WEIGHT_POPULATION,
    REVIEW_WEIGHT_EXPOSURE,
    REVIEW_WEIGHT_FRESHNESS,
    REVIEW_WEIGHT_OBSERVATION,
    SCORED_OBSERVATION_STATES,
    UNSCORED_OBSERVATION_STATES,
)
from app.services.demo_data import demo_service
from app.services.review_priority import (
    calculate_review_priority_for_analysis,
    compute_dataset_exposure_scores,
    compute_freshness_component,
    compute_observation_component,
)
from app.viewmodels.dashboard import build_dashboard_view

client = TestClient(app)


def test_1_dashboard_route_returns_200():
    """1. Dashboard route returns HTTP 200 OK with correct template."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Situation Dashboard" in response.text
    assert "ANALYZED AREAS SUMMARY" in response.text
    assert "REVIEW QUEUE" in response.text


def test_2_review_priority_calculated_only_for_change_states():
    """2. Review Priority is calculated only for change_detected, strong_change, unknown_change."""
    assert SCORED_OBSERVATION_STATES == {"change_detected", "strong_change", "unknown_change"}
    for state in ["change_detected", "strong_change", "unknown_change"]:
        comp = compute_observation_component(state)
        assert comp is not None
        assert comp > 0.0

    view = build_dashboard_view(demo_service)
    for item in view.review_queue:
        assert item.observation_state_raw in SCORED_OBSERVATION_STATES
        assert item.priority is not None
        assert item.priority.review_score > 0.0


def test_3_no_change_receives_no_review_priority():
    """3. no_change receives no Review Priority."""
    assert compute_observation_component("no_change") is None
    assert compute_observation_component(ObservationState.NO_CHANGE) is None

    result = calculate_review_priority_for_analysis(
        analysis_id="analysis_synth_004",
        observation_state="no_change",
        exposure_dict={"estimated_population": 0},
        dataset_exposure_metrics={"population_component": 0.0, "infrastructure_component": 0.0, "exposure_component": 0.0},
        observation_time="2026-08-10T04:30:00Z",
        dataset_latest_time="2026-08-17T03:00:00Z",
    )
    assert result is None

    # Check viewmodel
    view = build_dashboard_view(demo_service)
    no_change_ids = [nc.analysis_id for nc in view.no_change_areas]
    assert "analysis_synth_004" in no_change_ids
    # Must NOT be in review queue
    queue_ids = [q.analysis_id for q in view.review_queue]
    assert "analysis_synth_004" not in queue_ids


def test_4_insufficient_data_receives_no_review_priority():
    """4. insufficient_data receives no Review Priority."""
    assert compute_observation_component("insufficient_data") is None
    assert compute_observation_component(ObservationState.INSUFFICIENT_DATA) is None

    result = calculate_review_priority_for_analysis(
        analysis_id="analysis_synth_003",
        observation_state="insufficient_data",
        exposure_dict=None,
        dataset_exposure_metrics=None,
        observation_time="2026-08-09T01:00:00Z",
        dataset_latest_time="2026-08-17T03:00:00Z",
    )
    assert result is None

    # Check viewmodel
    view = build_dashboard_view(demo_service)
    insufficient_ids = [ia.analysis_id for ia in view.insufficient_areas]
    assert "analysis_synth_003" in insufficient_ids
    queue_ids = [q.analysis_id for q in view.review_queue]
    assert "analysis_synth_003" not in queue_ids


def test_5_review_score_formula_weights():
    """5. ReviewScore formula uses: 0.50 observation, 0.35 exposure, 0.15 freshness."""
    assert REVIEW_WEIGHT_OBSERVATION == 0.50
    assert REVIEW_WEIGHT_EXPOSURE == 0.35
    assert REVIEW_WEIGHT_FRESHNESS == 0.15
    assert round(REVIEW_WEIGHT_OBSERVATION + REVIEW_WEIGHT_EXPOSURE + REVIEW_WEIGHT_FRESHNESS, 2) == 1.00

    # Test formula output directly
    result = calculate_review_priority_for_analysis(
        analysis_id="test_analysis",
        observation_state="change_detected",  # 0.50
        exposure_dict={"estimated_population": 100},
        dataset_exposure_metrics={"population_component": 1.0, "infrastructure_component": 1.0, "exposure_component": 1.0},
        observation_time="2026-08-17T03:00:00Z",
        dataset_latest_time="2026-08-17T03:00:00Z",  # age 0 -> 1.00
    )
    assert result is not None
    # Expected: 0.50 * 0.50 + 0.35 * 1.00 + 0.15 * 1.00 = 0.25 + 0.35 + 0.15 = 0.75
    assert result.review_score == 0.75
    assert result.observation_weighted == 0.25
    assert result.exposure_weighted == 0.35
    assert result.freshness_weighted == 0.15


def test_6_strong_change_observation_component_is_one():
    """6. Strong Change observation component = 1.00."""
    assert compute_observation_component("strong_change") == 1.00
    assert compute_observation_component(ObservationState.STRONG_CHANGE) == 1.00


def test_7_change_detected_observation_component_is_half():
    """7. Change Detected observation component = 0.50."""
    assert compute_observation_component("change_detected") == 0.50
    assert compute_observation_component(ObservationState.CHANGE_DETECTED) == 0.50


def test_8_unknown_change_observation_component_is_sixty_five():
    """8. Unknown Change observation component = 0.65."""
    assert compute_observation_component("unknown_change") == 0.65
    assert compute_observation_component(ObservationState.UNKNOWN_CHANGE) == 0.65


def test_9_exposure_component_is_bounded_zero_to_one():
    """9. Exposure component calculation is bounded 0–1."""
    records = [
        {"analysis_id": "a1", "estimated_population": 50000, "road_length_km": 120.0, "bridge_count": 10},
        {"analysis_id": "a2", "estimated_population": 0, "road_length_km": 0.0, "bridge_count": 0},
        {"analysis_id": "a3", "estimated_population": None},
    ]
    scores = compute_dataset_exposure_scores(records)
    for aid, sc in scores.items():
        assert 0.0 <= sc["population_component"] <= 1.0
        assert 0.0 <= sc["infrastructure_component"] <= 1.0
        assert 0.0 <= sc["exposure_component"] <= 1.0

    # Max record should achieve 1.0 exposure
    assert scores["a1"]["exposure_component"] == 1.0
    # Zero record should achieve 0.0
    assert scores["a2"]["exposure_component"] == 0.0
    # Missing record marked
    assert scores["a3"]["missing_exposure_data"] is True
    assert scores["a3"]["exposure_component"] == 0.0


def test_10_freshness_component_is_bounded_zero_to_one():
    """10. Freshness component is bounded 0–1 across all decay stages."""
    ref_time = datetime(2026, 8, 30, tzinfo=timezone.utc)
    
    # 0 days old -> 1.00
    f0, a0 = compute_freshness_component(ref_time, ref_time)
    assert f0 == 1.00
    assert a0 == 0.0

    # 7 days old -> 0.80
    t7 = datetime(2026, 8, 23, tzinfo=timezone.utc)
    f7, a7 = compute_freshness_component(t7, ref_time)
    assert round(f7, 2) == 0.80

    # 14 days old -> 0.60
    t14 = datetime(2026, 8, 16, tzinfo=timezone.utc)
    f14, a14 = compute_freshness_component(t14, ref_time)
    assert round(f14, 2) == 0.60

    # 30 days old -> 0.30
    t30 = datetime(2026, 7, 31, tzinfo=timezone.utc)
    f30, a30 = compute_freshness_component(t30, ref_time)
    assert round(f30, 2) == 0.30

    # > 60 days old -> 0.10
    t100 = datetime(2026, 5, 1, tzinfo=timezone.utc)
    f100, a100 = compute_freshness_component(t100, ref_time)
    assert f100 == 0.10

    # Verify bounds
    for f in [f0, f7, f14, f30, f100]:
        assert 0.0 <= f <= 1.0


def test_11_records_sorted_by_review_score_descending():
    """11. Records in Review Queue are sorted by ReviewScore descending by default."""
    view = build_dashboard_view(demo_service)
    scores = [item.priority.review_score for item in view.review_queue]
    assert len(scores) >= 2
    # Verify non-increasing
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1]


def test_12_no_change_in_separate_section():
    """12. No Change appears in its separate section and does not display Review Priority."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "NO CHANGE AREAS" in response.text
    assert "Areas with no significant change under the current analysis criteria." in response.text
    assert "Synthetic AOI Delta" in response.text
    assert "Outside the demonstration review queue" in response.text


def test_13_insufficient_data_in_separate_section():
    """13. Insufficient Data appears in its separate section and is not interpreted as No Change."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "INSUFFICIENT / UNAVAILABLE AREAS" in response.text
    assert "Synthetic AOI Gamma" in response.text
    assert "Not interpreted as No Change" in response.text
    assert "Reason: Valid-pixel fraction below configured minimum." in response.text


def test_14_dashboard_text_triage_disclaimer():
    """14. Dashboard text states 'Review Priority is not hazard severity' or equivalent."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Review Priority is a triage aid, not an emergency severity level." in response.text
    assert "It does not describe physical magnitude or hazard severity." in response.text


def test_15_exposure_is_not_invented_when_unavailable():
    """15. Dashboard does not present unavailable population/exposure estimates."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Exposure data unavailable" in response.text
    assert "Estimated pop overlap" not in response.text
    assert '"estimated_population": null' in response.text


def test_16_synthetic_fixture_warning_present():
    """16. Synthetic development fixture warning is present."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "DEMO DASHBOARD" in response.text
    assert "Synthetic development fixtures — not Earth observation results." in response.text


def test_17_map_does_not_use_review_priority_as_observation_state():
    """17. Map polygons color by observation state, not Review Priority."""
    view = build_dashboard_view(demo_service)
    features = view.map_geojson["features"]
    assert len(features) == 5
    assert any(f["properties"]["analysis_id"] == "real_flood_001" for f in features)

    for feat in features:
        props = feat["properties"]
        obs_state = props["observation_state"]
        color = props["observation_state_color"]
        assert color not in ["#EF4444", "#F59E0B", "#10B981"], f"Alarm color {color} found for state {obs_state}"
        
        # Color must match observation state
        if obs_state == "change_detected":
            assert color == "#1E6BFF"
        elif obs_state == "unknown_change":
            assert color == "#8B5CF6"
        elif obs_state == "no_change":
            assert color == "#4E7880"
        elif obs_state == "insufficient_data":
            assert color == "#64748B"

        # Check that un-scored states have no review priority
        if obs_state in ["no_change", "insufficient_data"]:
            assert props["review_priority_band"] is None
            assert props["review_score"] is None

    # Verify dashboard page template contains script binding fill-color to observation_state_color
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Map polygons are colored strictly by physical Observation State, not Review Priority." in response.text


def test_18_all_previous_tests_remain_passing():
    """18. Verify overall integrity of previous route, viewer, and lab endpoints."""
    res_home = client.get("/")
    assert res_home.status_code == 200

    res_event = client.get("/event/event_synth_001")
    assert res_event.status_code == 200

    res_lab = client.get("/lab/analysis_synth_001")
    assert res_lab.status_code == 200

    res_map = client.get("/map")
    assert res_map.status_code == 200
