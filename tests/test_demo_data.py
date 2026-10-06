"""
Data model and synthetic fixture validation tests for NISAR Surface Change Explorer.
Step 3: Structured Demo Data Model + Seeded JSON/GeoJSON
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Domain, ObservationState
from app.services.demo_data import DemoDataService, demo_service


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_fixture_loading_and_validation():
    """1 & 2. Verify all fixture files load and validate against Pydantic models."""
    service = DemoDataService()
    assert len(service.get_aois()) >= 3
    assert len(service.get_acquisitions()) >= 4
    assert len(service.get_analyses()) >= 4
    assert len(service.get_events()) >= 4


def test_aoi_foreign_key_integrity():
    """3. Verify all AOI IDs referenced by analyses exist in aois.json."""
    aoi_ids = {a.id for a in demo_service.get_aois()}
    for analysis in demo_service.get_analyses():
        assert analysis.aoi_id in aoi_ids, f"Analysis {analysis.id} references non-existent AOI {analysis.aoi_id}"


def test_acquisition_foreign_key_integrity():
    """4. Verify acquisition IDs referenced by analyses exist where specified."""
    acq_ids = {acq.id for acq in demo_service.get_acquisitions()}
    for analysis in demo_service.get_analyses():
        if analysis.before_acquisition_id:
            assert analysis.before_acquisition_id in acq_ids, (
                f"Analysis {analysis.id} references missing before_acquisition {analysis.before_acquisition_id}"
            )
        if analysis.after_acquisition_id:
            assert analysis.after_acquisition_id in acq_ids, (
                f"Analysis {analysis.id} references missing after_acquisition {analysis.after_acquisition_id}"
            )


def test_manifest_integrity():
    """5. Verify manifest IDs referenced by analyses and events exist in manifests.json."""
    for analysis in demo_service.get_analyses():
        manifest = demo_service.get_manifest(analysis.manifest_id)
        assert manifest is not None, f"Analysis {analysis.id} references missing manifest {analysis.manifest_id}"
        assert manifest.analysis_id == analysis.id

    for event in demo_service.get_events():
        manifest = demo_service.get_manifest(event.manifest_id)
        assert manifest is not None, f"Event {event.id} references missing manifest {event.manifest_id}"


def test_region_analysis_id_integrity():
    """6. Verify all region analysis IDs exist in analyses.json."""
    analysis_ids = {a.id for a in demo_service.get_analyses()}
    for region in demo_service.change_regions.values():
        assert region.analysis_id in analysis_ids, (
            f"Region {region.id} references missing analysis {region.analysis_id}"
        )


def test_candidate_region_id_integrity():
    """7. Verify candidate region IDs exist and test multi-candidate support."""
    region_ids = set(demo_service.change_regions.keys())
    multi_candidate_found = False

    for region_id in region_ids:
        candidates = demo_service.get_candidates_for_region(region_id)
        if len(candidates) >= 2:
            multi_candidate_found = True
        for candidate in candidates:
            assert candidate.region_id in region_ids
            assert candidate.analysis_id in {a.id for a in demo_service.get_analyses()}

    assert multi_candidate_found, "At least one region should have multiple competing candidates"


def test_unknown_change_unclassified_model():
    """8. Verify unknown_change can use domain=unclassified."""
    unknown_analyses = [
        a for a in demo_service.get_analyses() 
        if a.observation_state == ObservationState.UNKNOWN_CHANGE
    ]
    assert len(unknown_analyses) >= 1
    for a in unknown_analyses:
        assert a.domain == Domain.UNCLASSIFIED
        assert a.classification_status.value == "unclassified"


def test_insufficient_data_quality_gate():
    """9. Verify insufficient_data analysis has quality_gate_passed=false."""
    insufficient_analyses = [
        a for a in demo_service.get_analyses() 
        if a.observation_state == ObservationState.INSUFFICIENT_DATA
    ]
    assert len(insufficient_analyses) >= 1
    for a in insufficient_analyses:
        assert a.quality.quality_gate_passed is False
        assert a.quality.valid_pixel_fraction < 0.5


def test_demo_api_endpoints(client):
    """10. Verify all /api/demo/ routes return 200 OK and maintain synthetic markers."""
    # List endpoints
    res_aois = client.get("/api/demo/aois")
    assert res_aois.status_code == 200
    assert len(res_aois.json()) >= 3
    assert res_aois.json()[0]["is_demo"] is True

    res_events = client.get("/api/demo/events")
    assert res_events.status_code == 200
    assert len(res_events.json()) >= 4

    # Detail endpoints
    sample_aoi_id = res_aois.json()[0]["id"]
    res_aoi = client.get(f"/api/demo/aois/{sample_aoi_id}")
    assert res_aoi.status_code == 200
    assert res_aoi.json()["id"] == sample_aoi_id

    sample_event_id = res_events.json()[0]["id"]
    res_event = client.get(f"/api/demo/events/{sample_event_id}")
    assert res_event.status_code == 200
    assert res_event.json()["id"] == sample_event_id

    sample_analysis_id = "analysis_synth_001"
    res_analysis = client.get(f"/api/demo/analyses/{sample_analysis_id}")
    assert res_analysis.status_code == 200
    assert res_analysis.json()["id"] == sample_analysis_id

    res_regions = client.get(f"/api/demo/analyses/{sample_analysis_id}/regions")
    assert res_regions.status_code == 200
    assert len(res_regions.json()) >= 1

    sample_region_id = "region_synth_002"
    res_candidates = client.get(f"/api/demo/regions/{sample_region_id}/candidates")
    assert res_candidates.status_code == 200
    assert len(res_candidates.json()) == 2

    sample_manifest_id = "manifest_synth_001"
    res_manifest = client.get(f"/api/demo/manifests/{sample_manifest_id}")
    assert res_manifest.status_code == 200
    assert res_manifest.json()["manifest_id"] == sample_manifest_id


def test_geojson_endpoint(client):
    """11 & 12. Verify GeoJSON endpoint returns FeatureCollection with valid region IDs."""
    response = client.get("/api/demo/change-regions.geojson")
    assert response.status_code == 200
    assert "geo+json" in response.headers["content-type"] or "json" in response.headers["content-type"]
    
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 2
    
    for feature in data["features"]:
        assert feature["type"] == "Feature"
        assert "geometry" in feature
        props = feature["properties"]
        assert "region_id" in props
        assert "analysis_id" in props
        assert isinstance(props["is_demo"], bool)
        expected_origin = "synthetic_ui_fixture" if props["is_demo"] else "precomputed_real_analysis"
        assert props["data_origin"] == expected_origin

    assert {feature["properties"]["is_demo"] for feature in data["features"]} == {True, False}
