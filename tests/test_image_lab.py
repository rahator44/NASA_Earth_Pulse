"""
Test Suite for Step 9: Scientist Image Lab.
Verifies lab metrics fixtures, API endpoints, scientist inspection workspace,
histogram rendering, threshold preview safety rules, domain awareness, and provenance.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.evidence import EvidenceLayer
from app.models.lab_metrics import AnalysisLabMetrics
from app.services.demo_data import demo_service

client = TestClient(app)


def test_1_lab_metrics_fixtures_validate():
    """1. Lab metrics fixtures validate against Pydantic schema."""
    assert len(demo_service.lab_metrics) >= 4
    for analysis_id, metrics in demo_service.lab_metrics.items():
        assert isinstance(metrics, AnalysisLabMetrics)
        assert metrics.analysis_id == analysis_id
        assert metrics.is_synthetic == (metrics.data_origin.value == "synthetic_ui_fixture")
        if metrics.is_synthetic:
            assert "Synthetic" in metrics.disclaimer or "synthetic" in metrics.disclaimer.lower()


def test_2_lab_metrics_api_returns_200():
    """2. Lab metrics API returns 200 for valid analysis."""
    response = client.get("/api/demo/analyses/analysis_synth_001/lab-metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["analysis_id"] == "analysis_synth_001"
    assert data["is_synthetic"] is True
    assert data["active_channel"] == "HH"
    assert "threshold_preview" in data
    assert data["threshold_preview"]["default"] == -3.8


def test_3_invalid_lab_metrics_request_returns_404():
    """3. Invalid lab metrics request returns 404."""
    response = client.get("/api/demo/analyses/non_existent_analysis/lab-metrics")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_4_lab_valid_analysis_id_returns_200():
    """4. /lab/{valid_analysis_id} returns 200."""
    response = client.get("/lab/analysis_synth_001")
    assert response.status_code == 200
    assert "Scientist Image Lab" in response.text
    assert "analysis_synth_001" in response.text

    # Also supports demo alias
    alias_resp = client.get("/lab/demo")
    assert alias_resp.status_code == 200
    assert "demo" in alias_resp.text


def test_5_invalid_analysis_id_returns_404():
    """5. Invalid analysis ID returns 404 with styled page."""
    response = client.get("/lab/invalid_analysis_xyz")
    assert response.status_code == 404
    assert "ANALYSIS NOT FOUND" in response.text
    assert "The requested analysis" in response.text
    assert "invalid_analysis_xyz" in response.text
    assert "Change Feed" in response.text
    assert "Explore Map" in response.text


def test_6_scientist_lab_includes_step_8_evidence_viewer():
    """6. Scientist Image Lab includes the Step 8 evidence viewer."""
    response = client.get("/lab/analysis_synth_001")
    assert response.status_code == 200
    # Checks for Step 8 viewer elements and controller
    assert "initEvidenceViewer" in response.text
    assert "Swipe" in response.text
    assert "Before" in response.text
    assert "After" in response.text
    assert "Difference" in response.text
    assert "Change Mask" in response.text


def test_7_synthetic_analysis_shows_demo_lab_warning():
    """7. Synthetic analysis shows DEMO LAB warning persistently."""
    response = client.get("/lab/analysis_synth_001")
    assert response.status_code == 200
    assert "DEMO LAB" in response.text
    assert (
        "Synthetic evidence and analysis controls are used to demonstrate the scientist workflow. "
        "These are not NISAR measurements." in response.text
    )


def test_8_histogram_renders_when_histogram_fixture_exists():
    """8. Histogram renders when histogram fixture exists."""
    response = client.get("/lab/analysis_synth_001")
    assert response.status_code == 200
    assert "Synthetic distribution — demonstration only." in response.text
    assert "Synthetic distribution used to demonstrate analysis controls." in response.text
    assert "<svg viewBox=\"0 0 540 180\"" in response.text
    assert "Radar Backscatter Difference Distribution" in response.text


def test_9_threshold_slider_renders_only_when_threshold_preview_exists():
    """9. Threshold slider renders only when threshold preview exists."""
    response = client.get("/lab/analysis_synth_001")
    assert response.status_code == 200
    assert "THRESHOLD PREVIEW" in response.text
    assert 'id="threshold-slider"' in response.text
    assert 'min="-5.0"' in response.text
    assert 'max="-2.0"' in response.text
    assert "RESET" in response.text


def test_10_insufficient_data_analysis_does_not_show_threshold_controls():
    """10. insufficient_data analysis does not show threshold controls."""
    # analysis_synth_003 has quality_gate_passed = False
    response = client.get("/lab/analysis_synth_003")
    assert response.status_code == 200
    assert (
        "Threshold analysis unavailable because the quality gate was not passed."
        in response.text
    )
    # Threshold slider should NOT be rendered
    assert 'id="threshold-slider"' not in response.text
    assert "PREVIEW MODE" not in response.text


def test_11_threshold_control_contains_preview_only_wording():
    """11. Threshold control contains 'Preview only' wording."""
    response = client.get("/lab/analysis_synth_001")
    assert response.status_code == 200
    assert "Preview only. Stored analysis remains unchanged." in response.text
    assert "Preview uses precomputed synthetic mask states." in response.text


def test_12_channel_selector_does_not_display_unavailable_channels():
    """12. Channel selector does not display unavailable channels."""
    # analysis_synth_001 has available_channels = ["HH", "HV"]
    response = client.get("/lab/analysis_synth_001")
    assert response.status_code == 200
    # Should render available channels
    assert "HH" in response.text
    assert "HV" in response.text
    # Should not present clickable buttons for channels not in available_channels (e.g. VV, VH)
    assert "@click=\"selectChannel('VV')\"" not in response.text
    assert "@click=\"selectChannel('VH')\"" not in response.text

    # Single-channel analysis (analysis_synth_004) displays read-only fixture
    single_chan_resp = client.get("/lab/analysis_synth_004")
    assert single_chan_resp.status_code == 200
    assert "SYNTHETIC FIXTURE" in single_chan_resp.text


def test_13_acquisition_metadata_renders():
    """13. Acquisition metadata renders."""
    response = client.get("/lab/analysis_synth_001")
    assert response.status_code == 200
    assert "ACQUISITION METADATA" in response.text
    assert "BEFORE ACQUISITION (REFERENCE)" in response.text
    assert "AFTER ACQUISITION (SECONDARY)" in response.text
    # Check acquisition IDs are present
    assert "SYNTH_GCOV_A_001" in response.text
    assert "SYNTH_GCOV_A_002" in response.text
    assert "Ascending" in response.text


def test_14_manifest_id_renders():
    """14. Manifest ID renders."""
    response = client.get("/lab/analysis_synth_001")
    assert response.status_code == 200
    assert "MANIFEST: manifest_synth_001" in response.text
    assert "manifest_synth_001" in response.text


def test_15_validation_section_renders():
    """15. Validation section renders."""
    response = client.get("/lab/analysis_synth_001")
    assert response.status_code == 200
    assert "VALIDATION BENCHMARK" in response.text
    assert "Validated on 2 independent event(s)." in response.text
    assert "SYNTH_GAUGE_COVARIANCE_MOCK" in response.text
    assert "Precision" in response.text
    assert "Recall" in response.text


def test_16_deformation_analysis_does_not_show_gcov_backscatter_controls():
    """16. Deformation analysis does not display GCOV/backscatter-specific controls when not configured."""
    response = client.get("/lab/analysis_synth_004")
    assert response.status_code == 200
    assert "Ground Deformation" in response.text
    # Threshold preview not configured for deformation
    assert (
        "Threshold preview is not configured for this interferometric analysis."
        in response.text
    )
    # Does not render threshold slider
    assert 'id="threshold-slider"' not in response.text


def test_17_synthetic_evidencelayer_metadata_defaults():
    """17. Synthetic EvidenceLayer no longer defaults misleadingly to real NISAR source/product/maturity/polarization values."""
    # Test model defaults
    layer = EvidenceLayer(
        url="/static/images/test.svg",
        label="Test Layer",
    )
    assert layer.source == "Synthetic visual fixture"
    assert layer.product is None
    assert layer.maturity is None
    assert layer.polarization is None

    # Test that stored fixture metadata is explicit
    evidence = demo_service.get_evidence_for_analysis("analysis_synth_001")
    assert evidence is not None
    assert evidence.before.source == "Synthetic visual fixture"
    assert "Synthetic" in evidence.before.product
    assert "Demonstration" in evidence.before.product
    assert "DEMO" in evidence.before.maturity


def test_18_pixel_inspector_option_a_disclaimer():
    """18. Pixel inspector displays Option A disclaimer and normalized coordinates."""
    response = client.get("/lab/analysis_synth_001")
    assert response.status_code == 200
    assert "CURSOR POSITION:" in response.text
    assert (
        "Numeric pixel sampling becomes available with real raster evidence."
        in response.text
    )
