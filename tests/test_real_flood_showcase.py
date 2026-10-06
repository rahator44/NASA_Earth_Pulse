"""
Step 12: Real NISAR Flood Showcase Integration Tests.
Verifies end-to-end integration of precomputed real NISAR analysis (real_flood_001).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.enums import DataOrigin
from app.services.demo_data import demo_service

client = TestClient(app)


def test_1_real_event_loads():
    """1. Real event loads and returns 200 OK."""
    res = client.get("/event/real_flood_001")
    assert res.status_code == 200
    assert "Lake Henderson / Atchafalaya Basin" in res.text
    assert "REAL NISAR ANALYSIS" in res.text


def test_2_real_event_uses_precomputed_real_analysis():
    """2. Real event uses precomputed_real_analysis data origin."""
    ev = demo_service.get_event("real_flood_001")
    assert ev is not None
    assert ev.data_origin == DataOrigin.PRECOMPUTED_REAL_ANALYSIS
    assert ev.is_demo is False


def test_3_real_event_does_not_show_synthetic_disclaimer():
    """3. Real event does not show synthetic disclaimer or demo fixture badge."""
    res = client.get("/event/real_flood_001")
    assert "DEMO FIXTURE" not in res.text
    assert "Synthetic development fixture" not in res.text
    assert "Synthetic visual fixture" not in res.text


def test_4_home_shows_real_nisar_showcase():
    """4. Home separates the real NISAR analysis from demo fixtures."""
    res = client.get("/")
    assert res.status_code == 200
    assert "REAL NISAR ANALYSIS" in res.text
    assert "Lake Henderson / Atchafalaya Basin" in res.text
    assert "2026-06-28 → 2026-07-10" in res.text
    assert "0.837 km²" in res.text
    assert "NASA NISAR / ASF DAAC" in res.text


def test_5_real_event_detail_shows_correct_acquisition_dates():
    """5. Real Event Detail shows correct acquisition dates."""
    res = client.get("/event/real_flood_001")
    assert "28 Jun 2026" in res.text or "2026-06-28" in res.text
    assert "10 Jul 2026" in res.text or "2026-07-10" in res.text
    assert "Track 33 / Frame 17" in res.text


def test_6_real_measured_area_from_stored_output():
    """6. Real measured area = 0.837 km² from stored output."""
    ev = demo_service.get_event("real_flood_001")
    assert ev.primary_measurement_value == "0.837 km²"

    res = client.get("/event/real_flood_001")
    assert "0.837 km²" in res.text


def test_7_real_evidence_viewer_assets_load():
    """7. Real Evidence Viewer assets load successfully (HTTP 200)."""
    for path in [
        "/static/real/before_db_preview.png",
        "/static/real/after_db_preview.png",
        "/static/real/diff_db_colormap.png",
        "/static/real/change_mask_overlay.png",
        "/static/real/before_with_change_overlay.png"
    ]:
        res = client.get(path)
        assert res.status_code == 200, f"Asset failed to load: {path}"
        assert len(res.content) > 1000


def test_8_real_image_lab_histogram_loads():
    """8. Real Image Lab histogram loads with measured distribution."""
    res = client.get("/lab/real_flood_001")
    assert res.status_code == 200
    assert "REAL NISAR ANALYSIS" in res.text
    assert "DEMO LAB" not in res.text
    assert "Radar Backscatter Difference Distribution" in res.text
    assert "Measured distribution from provisional NISAR L2 GCOV" in res.text


def test_9_real_map_aoi_and_change_geojson_loads():
    """9. Real map AOI and change GeoJSON load."""
    res_aois = client.get("/api/demo/aois.geojson")
    assert res_aois.status_code == 200
    aoi_features = res_aois.json()["features"]
    real_aoi_found = any(f["properties"]["id"] == "aoi_real_001" for f in aoi_features)
    assert real_aoi_found

    res_cr = client.get("/api/demo/change-regions.geojson")
    assert res_cr.status_code == 200
    cr_features = res_cr.json()["features"]
    real_cr_found = any(f["properties"].get("analysis_id") == "real_flood_001" for f in cr_features)
    assert real_cr_found


def test_10_map_inspector_returns_real_analysis():
    """10. Map inspector returns real analysis for Lake Henderson selection."""
    payload = {
        "aoi_id": "aoi_real_001",
        "selection_type": "point"
    }
    res = client.post("/api/demo/inspect-area", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["has_processed_analysis"] is True
    assert data["is_demo"] is False
    assert len(data["matches"]) >= 1
    match = data["matches"][0]
    assert match["analysis_id"] == "real_flood_001"
    assert match["is_demo"] is False
    assert match["disclaimer"] == ""


def test_11_no_synthetic_exposure_is_attached():
    """11. No synthetic exposure is attached; exposure shows unavailable."""
    exp = demo_service.get_exposure_for_analysis("real_flood_001")
    assert exp is None

    res = client.get("/event/real_flood_001")
    assert "Exposure data unavailable" in res.text
    assert "Synthetic development fixture" not in res.text


def test_12_methods_status_is_updated_accurately():
    """12. Methods capability status table is updated accurately."""
    res = client.get("/methods")
    assert res.status_code == 200
    assert "IMPLEMENTED — ONE PRECOMPUTED SHOWCASE" in res.text
    assert "IMPLEMENTED — ONE REAL EVENT" in res.text
    assert "NOT YET IMPLEMENTED — BLOCKED AT EARTHDATA AUTHENTICATION" not in res.text
