"""
Tests for Step 5 — Interactive Map Selection + Area Inspector.
Verifies spatial queries, scientific state separation, and API contracts.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_map_page_renders_200():
    """Requirement 9: GET /map returns 200 with required interactive controls."""
    response = client.get("/map")
    assert response.status_code == 200
    html = response.text
    # Verify Step 5 toolbar controls and containers
    assert "id=\"tool-click\"" in html
    assert "id=\"tool-rectangle\"" in html
    assert "id=\"tool-polygon\"" in html
    assert "id=\"tool-clear\"" in html
    assert "id=\"select-demo-area\"" in html
    assert "id=\"area-inspector-content\"" in html
    assert "DEMO DATA" in html
    assert "area_inspector.js" in html
    assert "map_selection.js" in html
    assert "map.js" in html


def test_inspect_point_inside_synthetic_aoi():
    """Requirement 1: POST /api/demo/inspect-area with point inside synthetic AOI returns matching analysis."""
    # Point inside Synthetic AOI Alpha (lon -25.1, lat 15.1)
    payload = {
        "geometry": {
            "type": "Point",
            "coordinates": [-25.1, 15.1]
        },
        "selection_type": "point"
    }
    response = client.post("/api/demo/inspect-area", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["has_processed_analysis"] is True
    assert data["matched_count"] == 1
    assert "aoi_synth_alpha" in data["matched_aoi_ids"]
    assert len(data["matches"]) == 1

    match = data["matches"][0]
    assert match["aoi_id"] == "aoi_synth_alpha"
    assert match["aoi_display_name"] == "Synthetic AOI Alpha"
    assert match["observation_state_raw"] == "change_detected"
    assert match["observation_state_label"] == "CHANGE DETECTED"
    assert match["domain_raw"] == "flood_wetland"
    assert match["domain_label"] == "Flood / Wetland"
    assert match["manifest_id"] == "manifest_synth_001"
    assert match["primary_measurement_label"] == "Inundated Extent"
    assert match["primary_measurement_value"] == "4.8 km²"
    assert match["is_demo"] is True
    assert "Synthetic development fixture" in match["disclaimer"]


def test_inspect_point_outside_every_aoi():
    """Requirement 2: Point outside every AOI returns has_processed_analysis = false."""
    # Point in Gulf of Guinea / Prime Meridian intersection (lon 0, lat 0)
    payload = {
        "geometry": {
            "type": "Point",
            "coordinates": [0.0, 0.0]
        },
        "selection_type": "point"
    }
    response = client.post("/api/demo/inspect-area", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["has_processed_analysis"] is False
    assert data["matched_count"] == 0
    assert data["matched_aoi_ids"] == []
    assert data["matches"] == []
    assert data["notice"] is not None
    assert "No processed surface-change analysis is available" in data["notice"]


def test_no_match_does_not_return_no_change_state():
    """Requirement 4: No-match response does NOT return observation_state = no_change or insufficient_data."""
    payload = {
        "geometry": {
            "type": "Point",
            "coordinates": [120.0, -25.0]
        },
        "selection_type": "point"
    }
    response = client.post("/api/demo/inspect-area", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Must NOT have any observation state assigned to unmatched space
    assert data["has_processed_analysis"] is False
    assert len(data["matches"]) == 0
    # Ensure no observation_state leaked to top-level
    assert "observation_state" not in data or data.get("observation_state") is None


def test_polygon_intersecting_multiple_aois():
    """Requirement 3: Polygon intersecting multiple AOIs returns all matches."""
    # Polygon bounding box covering both AOI Alpha and AOI Beta
    payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-30.0, -20.0],
                    [20.0, -20.0],
                    [20.0, 20.0],
                    [-30.0, 20.0],
                    [-30.0, -20.0]
                ]
            ]
        },
        "selection_type": "polygon"
    }
    response = client.post("/api/demo/inspect-area", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["has_processed_analysis"] is True
    assert data["matched_count"] == 2
    assert "aoi_synth_alpha" in data["matched_aoi_ids"]
    assert "aoi_synth_beta" in data["matched_aoi_ids"]
    assert len(data["matches"]) == 2

    aoi_names = [m["aoi_display_name"] for m in data["matches"]]
    assert "Synthetic AOI Alpha" in aoi_names
    assert "Synthetic AOI Beta" in aoi_names


def test_insufficient_data_remains_insufficient_data():
    """Requirement 5: insufficient_data analysis remains insufficient_data with stored quality reasons."""
    # Point inside AOI Gamma (lon 45.0, lat 30.0)
    payload = {
        "geometry": {
            "type": "Point",
            "coordinates": [45.0, 30.0]
        },
        "selection_type": "point"
    }
    response = client.post("/api/demo/inspect-area", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["has_processed_analysis"] is True
    match = data["matches"][0]
    assert match["aoi_id"] == "aoi_synth_gamma"
    assert match["observation_state_raw"] == "insufficient_data"
    assert match["observation_state_label"] == "INSUFFICIENT DATA"
    assert match["quality_gate_passed"] is False
    assert "Valid-pixel fraction below configured minimum" in match["quality_notes"]
    # Change measurements must NOT be displayed for insufficient data
    assert match["primary_measurement_label"] is None
    assert match["primary_measurement_value"] is None


def test_unknown_change_remains_unclassified_with_candidate_matches():
    """Requirement 6 & 7: unknown_change remains unclassified and exposes competing candidate hypotheses."""
    # Point inside AOI Beta (lon 10.0, lat -15.0)
    payload = {
        "geometry": {
            "type": "Point",
            "coordinates": [10.0, -15.0]
        },
        "selection_type": "point"
    }
    response = client.post("/api/demo/inspect-area", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["has_processed_analysis"] is True
    match = data["matches"][0]
    assert match["aoi_id"] == "aoi_synth_beta"
    assert match["observation_state_raw"] == "unknown_change"
    assert match["observation_state_label"] == "UNKNOWN CHANGE"
    assert match["domain_raw"] == "unclassified"
    assert match["domain_label"] == "Unclassified Change"

    # Must contain candidate interpretations
    assert len(match["candidates"]) == 2
    candidate_domains = [c["candidate_domain"] for c in match["candidates"]]
    assert "flood_wetland" in candidate_domains
    assert "wildfire" in candidate_domains
    # Neither candidate is confirmed
    assert all(not c["supported"] for c in match["candidates"])


def test_candidate_matches_direct_endpoint():
    """Requirement 7: Candidate matches can be retrieved for an ambiguous region via API."""
    response = client.get("/api/demo/regions/region_synth_002/candidates")
    assert response.status_code == 200
    candidates = response.json()
    assert len(candidates) == 2
    domains = [c["candidate_domain"] for c in candidates]
    assert "flood_wetland" in domains
    assert "wildfire" in domains


def test_change_regions_geojson_endpoint():
    """Requirement 8: Existing /api/demo/change-regions.geojson returns FeatureCollection."""
    response = client.get("/api/demo/change-regions.geojson")
    assert response.status_code == 200
    geojson = response.json()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) >= 2
    # Ensure properties exist
    first_feat = geojson["features"][0]
    assert "region_id" in first_feat["properties"]
    assert "analysis_id" in first_feat["properties"]
    assert "classification_status" in first_feat["properties"]


def test_aois_geojson_endpoint():
    """Validates /api/demo/aois.geojson provides MapLibre-ready AOI boundaries."""
    response = client.get("/api/demo/aois.geojson")
    assert response.status_code == 200
    geojson = response.json()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) >= 4


def test_inspect_direct_aoi_id_lookup():
    """Validates direct AOI lookup (e.g., from Find Demo Area dropdown or URL parameter)."""
    payload = {
        "aoi_id": "aoi_synth_delta",
        "selection_type": "point"
    }
    response = client.post("/api/demo/inspect-area", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_processed_analysis"] is True
    assert len(data["matches"]) == 1
    match = data["matches"][0]
    assert match["aoi_id"] == "aoi_synth_delta"
    assert match["observation_state_raw"] == "no_change"
    assert match["observation_state_label"] == "NO CHANGE"
    assert match["domain_label"] == "Ground Deformation"
