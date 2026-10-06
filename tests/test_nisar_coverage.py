"""
Unit and API integration tests for Step 6 — Real NISAR Coverage + Acquisition Discovery.
All tests use deterministic mocks to verify normalization and pairing rules without NASA uptime dependencies.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.coverage import (
    CoverageSearchRequest,
    CoverageSearchStatus,
    PairCompatibilityStatus,
)
from app.services.nisar_coverage import NisarCoverageService, coverage_service

client = TestClient(app)


class MockASFProduct:
    """Mock representing an item returned by asf_search.search."""
    def __init__(self, properties: dict, geometry: dict = None):
        self.properties = properties
        self.geometry = geometry or {
            "type": "Polygon",
            "coordinates": [[[-25.2, 14.9], [-24.8, 14.9], [-24.8, 15.3], [-25.2, 15.3], [-25.2, 14.9]]]
        }


def make_sample_gcov(
    scene_id: str,
    start_time: str,
    track: int = 42,
    frame: int = 110,
    direction: str = "ASCENDING",
    mode: str = "DBL",
    polarization: list = None,
    maturity: str = "PROVISIONAL",
    crid: str = "P05023",
    pge: str = "R05.02.3"
) -> MockASFProduct:
    return MockASFProduct({
        "sceneName": scene_id,
        "fileID": scene_id,
        "processingLevel": "GCOV",
        "startTime": start_time,
        "stopTime": start_time,
        "pathNumber": track,
        "frameNumber": frame,
        "flightDirection": direction,
        "beamModeType": mode,
        "polarization": polarization or ["HH", "HV"],
        "sensor": "L-SAR",
        "rangeBandwidth": ["5"],
        "pgeVersion": pge,
        "crid": crid,
        "dataMaturity": maturity,
        "url": f"https://datapool.asf.alaska.edu/GCOV/{scene_id}.h5"
    })


def test_valid_aoi_coverage_request_normalized(monkeypatch):
    """Requirement 1, 2, 3, 4: Valid AOI coverage request normalizes GCOV, GUNW, GOFF results."""
    def mock_asf_search(**kwargs):
        pl = kwargs.get("processingLevel")
        mat = kwargs.get("dataMaturity")
        if pl == "GCOV" and mat == "PROVISIONAL":
            return [make_sample_gcov("GCOV_P_001", "2026-08-01T10:15:00Z")]
        elif pl == "GUNW" and mat == "PROVISIONAL":
            return [MockASFProduct({
                "sceneName": "GUNW_P_001",
                "processingLevel": "GUNW",
                "startTime": "2026-08-05T04:30:00Z",
                "pathNumber": 112,
                "frameNumber": 320,
                "flightDirection": "DESCENDING"
            })]
        elif pl == "GOFF" and mat == "PROVISIONAL":
            return [MockASFProduct({
                "sceneName": "GOFF_P_001",
                "processingLevel": "GOFF",
                "startTime": "2026-08-02T12:00:00Z",
                "pathNumber": 88,
                "frameNumber": 204
            })]
        return []

    monkeypatch.setattr(coverage_service, "search_client", mock_asf_search)
    coverage_service._cache.clear()

    payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-25.5, 14.8], [-24.8, 14.8], [-24.8, 15.4], [-25.5, 15.4], [-25.5, 14.8]]]
        },
        "requested_products": ["GCOV", "GUNW", "GOFF"]
    }

    response = client.post("/api/coverage/search", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["search_status"] == "AVAILABLE"
    # Verify product categorization
    assert data["products"]["GCOV"]["total_count"] == 1
    assert data["products"]["GUNW"]["total_count"] == 1
    assert data["products"]["GOFF"]["total_count"] == 1

    # Verify GCOV normalization fields
    gcov_item = data["products"]["GCOV"]["provisional"]["acquisitions"][0]
    assert gcov_item["id"] == "GCOV_P_001"
    assert gcov_item["product_type"] == "GCOV"
    assert gcov_item["track"] == 42
    assert gcov_item["frame"] == 110
    assert gcov_item["orbit_direction"] == "ASCENDING"
    assert "HH" in gcov_item["polarizations"]
    assert gcov_item["beam_mode"] == "DBL"
    assert gcov_item["data_maturity"] == "PROVISIONAL"
    assert gcov_item["source"] == "NASA NISAR / ASF DAAC"
    assert gcov_item["data_origin"] == "live_metadata"


def test_provisional_and_beta_remain_separate(monkeypatch):
    """Requirement 5: PROVISIONAL and BETA results are kept distinct and never merged silently."""
    def mock_asf_search(**kwargs):
        pl = kwargs.get("processingLevel")
        mat = kwargs.get("dataMaturity")
        if pl == "GCOV" and mat == "PROVISIONAL":
            return [make_sample_gcov("GCOV_PROV", "2026-08-10T00:00:00Z", maturity="PROVISIONAL")]
        elif pl == "GCOV" and mat == "BETA":
            return [make_sample_gcov("GCOV_BETA", "2026-07-20T00:00:00Z", maturity="BETA")]
        return []

    monkeypatch.setattr(coverage_service, "search_client", mock_asf_search)
    coverage_service._cache.clear()

    payload = {
        "geometry": {"type": "Point", "coordinates": [-25.1, 15.1]},
        "requested_products": ["GCOV"]
    }
    response = client.post("/api/coverage/search", json=payload)
    assert response.status_code == 200
    data = response.json()

    gcov = data["products"]["GCOV"]
    assert gcov["provisional"]["count"] == 1
    assert gcov["beta"]["count"] == 1
    assert gcov["total_count"] == 2
    assert gcov["provisional"]["acquisitions"][0]["data_maturity"] == "PROVISIONAL"
    assert gcov["beta"]["acquisitions"][0]["data_maturity"] == "BETA"


def test_module_availability_derived_correctly(monkeypatch):
    """Requirement 6: Module availability derives data availability only, not physical change."""
    def mock_asf_search(**kwargs):
        pl = kwargs.get("processingLevel")
        if pl == "GCOV":
            return [make_sample_gcov("GCOV_SAMPLE", "2026-08-01T00:00:00Z")]
        elif pl == "GUNW":
            return [MockASFProduct({"sceneName": "GUNW_SAMPLE", "processingLevel": "GUNW", "startTime": "2026-08-01T00:00:00Z"})]
        return []

    monkeypatch.setattr(coverage_service, "search_client", mock_asf_search)
    coverage_service._cache.clear()

    payload = {
        "geometry": {"type": "Point", "coordinates": [-25.1, 15.1]},
        "requested_products": ["GCOV", "GUNW", "GOFF"]
    }
    response = client.post("/api/coverage/search", json=payload)
    assert response.status_code == 200
    avail = response.json()["module_availability"]

    assert avail["flood_wetland"] == "DATA AVAILABLE"
    assert avail["vegetation_disturbance"] == "DATA AVAILABLE"
    assert avail["deformation"] == "DATA AVAILABLE"
    assert avail["glacier"] == "PRODUCT NOT FOUND"


def test_zero_results_returns_no_results(monkeypatch):
    """Requirement 7: Zero metadata results returns NO_RESULTS rather than No Change."""
    def mock_empty_search(**kwargs):
        return []

    monkeypatch.setattr(coverage_service, "search_client", mock_empty_search)
    coverage_service._cache.clear()

    payload = {
        "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
        "requested_products": ["GCOV", "GUNW", "GOFF"]
    }
    response = client.post("/api/coverage/search", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["search_status"] == "NO_RESULTS"
    # Ensure no observation state leaked
    assert "observation_state" not in data


def test_network_exception_returns_service_unavailable(monkeypatch):
    """Requirement 8: Network or service exception returns SERVICE_UNAVAILABLE."""
    def mock_failing_search(**kwargs):
        raise ConnectionError("DNS resolution failed for asf.earthdatacloud.nasa.gov")

    monkeypatch.setattr(coverage_service, "search_client", mock_failing_search)
    coverage_service._cache.clear()

    payload = {
        "geometry": {"type": "Point", "coordinates": [-25.1, 15.1]}
    }
    response = client.post("/api/coverage/search", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["search_status"] == "SERVICE_UNAVAILABLE"
    assert "could not be queried" in data["error_message"]


def test_malformed_geometry_returns_http_400():
    """Requirement 9: Malformed GeoJSON returns HTTP 400."""
    payload = {
        "geometry": {"type": "InvalidPolygon", "coordinates": "invalid"}
    }
    response = client.post("/api/coverage/search", json=payload)
    assert response.status_code == 400


def test_excessive_search_area_rejected():
    """Requirement 10: Excessive search area exceeding span limit returns HTTP 400."""
    # Huge box spanning 10 degrees latitude and longitude
    payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-30.0, -10.0], [-10.0, -10.0], [-10.0, 10.0], [-30.0, 10.0], [-30.0, -10.0]]]
        }
    }
    response = client.post("/api/coverage/search", json=payload)
    assert response.status_code == 400
    assert "exceeds allowable size" in response.json()["detail"]


def test_cache_returns_repeated_result_without_second_call(monkeypatch):
    """Requirement 11: In-process cache returns repeated result without second ASF query."""
    call_count = {"count": 0}

    def counting_mock_search(**kwargs):
        call_count["count"] += 1
        return [make_sample_gcov("GCOV_CACHED", "2026-08-01T00:00:00Z")]

    monkeypatch.setattr(coverage_service, "search_client", counting_mock_search)
    coverage_service._cache.clear()

    payload = {"geometry": {"type": "Point", "coordinates": [-25.1, 15.1]}, "requested_products": ["GCOV"]}

    # First call
    r1 = client.post("/api/coverage/search", json=payload)
    assert r1.status_code == 200
    initial_calls = call_count["count"]
    assert initial_calls > 0

    # Second call (must be served from cache)
    r2 = client.post("/api/coverage/search", json=payload)
    assert r2.status_code == 200
    assert call_count["count"] == initial_calls


def test_gcov_nearest_earlier_pair_selection(monkeypatch):
    """Requirement 12: GCOV nearest-earlier pair selection correctly links chronologically compatible pairs."""
    def mock_pair_search(**kwargs):
        mat = kwargs.get("dataMaturity")
        if mat == "PROVISIONAL":
            return [
                make_sample_gcov("GCOV_EARLIER", "2026-08-01T10:15:00Z"),
                make_sample_gcov("GCOV_LATER", "2026-08-13T10:15:00Z")
            ]
        return []

    monkeypatch.setattr(coverage_service, "search_client", mock_pair_search)
    coverage_service._cache.clear()

    payload = {"geometry": {"type": "Point", "coordinates": [-25.1, 15.1]}, "requested_products": ["GCOV"]}
    response = client.post("/api/coverage/search", json=payload)
    assert response.status_code == 200
    candidates = response.json()["gcov_pair_candidates"]

    assert len(candidates) == 1
    pair = candidates[0]
    assert pair["before_id"] == "GCOV_EARLIER"
    assert pair["after_id"] == "GCOV_LATER"
    assert pair["temporal_baseline_days"] == 12
    assert pair["compatibility_status"] == "COMPATIBLE"


def test_beta_not_paired_with_provisional(monkeypatch):
    """Requirement 13: BETA acquisitions are never automatically paired with PROVISIONAL."""
    def mock_mixed_maturity(**kwargs):
        mat = kwargs.get("dataMaturity")
        if mat == "PROVISIONAL":
            return [make_sample_gcov("GCOV_P1", "2026-08-01T00:00:00Z", maturity="PROVISIONAL")]
        elif mat == "BETA":
            return [make_sample_gcov("GCOV_B1", "2026-08-13T00:00:00Z", maturity="BETA")]
        return []

    monkeypatch.setattr(coverage_service, "search_client", mock_mixed_maturity)
    coverage_service._cache.clear()

    payload = {"geometry": {"type": "Point", "coordinates": [-25.1, 15.1]}, "requested_products": ["GCOV"]}
    response = client.post("/api/coverage/search", json=payload)
    assert response.status_code == 200
    candidates = response.json()["gcov_pair_candidates"]
    # No pairs should be formed across PROVISIONAL and BETA
    assert len(candidates) == 0


def test_incompatible_track_rejects_pair():
    """Requirement 14: Incompatible track sets status to INCOMPATIBLE."""
    svc = NisarCoverageService()
    a1 = make_sample_gcov("A1", "2026-08-01T00:00:00Z", track=42)
    a2 = make_sample_gcov("A2", "2026-08-13T00:00:00Z", track=72)
    acq1 = svc._normalize_product(a1, "GCOV", "PROVISIONAL")
    acq2 = svc._normalize_product(a2, "GCOV", "PROVISIONAL")
    pair = svc._evaluate_gcov_pair(acq1, acq2)
    assert pair.compatibility_status == PairCompatibilityStatus.INCOMPATIBLE
    assert pair.checks.same_track is False


def test_incompatible_frame_rejects_pair():
    """Requirement 15: Incompatible frame sets status to INCOMPATIBLE."""
    svc = NisarCoverageService()
    a1 = make_sample_gcov("A1", "2026-08-01T00:00:00Z", frame=110)
    a2 = make_sample_gcov("A2", "2026-08-13T00:00:00Z", frame=115)
    acq1 = svc._normalize_product(a1, "GCOV", "PROVISIONAL")
    acq2 = svc._normalize_product(a2, "GCOV", "PROVISIONAL")
    pair = svc._evaluate_gcov_pair(acq1, acq2)
    assert pair.compatibility_status == PairCompatibilityStatus.INCOMPATIBLE
    assert pair.checks.same_frame is False


def test_incompatible_direction_rejects_pair():
    """Requirement 16: Incompatible orbit direction sets status to INCOMPATIBLE."""
    svc = NisarCoverageService()
    a1 = make_sample_gcov("A1", "2026-08-01T00:00:00Z", direction="ASCENDING")
    a2 = make_sample_gcov("A2", "2026-08-13T00:00:00Z", direction="DESCENDING")
    acq1 = svc._normalize_product(a1, "GCOV", "PROVISIONAL")
    acq2 = svc._normalize_product(a2, "GCOV", "PROVISIONAL")
    pair = svc._evaluate_gcov_pair(acq1, acq2)
    assert pair.compatibility_status == PairCompatibilityStatus.INCOMPATIBLE
    assert pair.checks.same_direction is False


def test_missing_required_metadata_insufficient_metadata():
    """Requirement 17: Missing required compatibility metadata produces INSUFFICIENT_METADATA."""
    svc = NisarCoverageService()
    a1 = make_sample_gcov("A1", "2026-08-01T00:00:00Z", mode=None)  # Mode missing
    a2 = make_sample_gcov("A2", "2026-08-13T00:00:00Z", mode="DBL")
    acq1 = svc._normalize_product(a1, "GCOV", "PROVISIONAL")
    acq2 = svc._normalize_product(a2, "GCOV", "PROVISIONAL")
    pair = svc._evaluate_gcov_pair(acq1, acq2)
    assert pair.compatibility_status == PairCompatibilityStatus.INSUFFICIENT_METADATA
    assert pair.checks.compatible_mode is None


def test_coverage_status_endpoint():
    """Validates lightweight GET /api/coverage/status."""
    response = client.get("/api/coverage/status")
    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert "asf_version" in data
    assert data["provisional_start_date"] == "2026-06-17"


def test_existing_inspect_area_still_works():
    """Requirement 18: Existing Step 5 /api/demo/inspect-area still works."""
    payload = {
        "geometry": {"type": "Point", "coordinates": [-25.1, 15.1]},
        "selection_type": "point"
    }
    response = client.post("/api/demo/inspect-area", json=payload)
    assert response.status_code == 200
    assert response.json()["has_processed_analysis"] is True


def test_existing_map_still_returns_200():
    """Requirement 19: Existing /map page still returns 200."""
    response = client.get("/map")
    assert response.status_code == 200
    assert "Map &amp; Coverage Explorer" in response.text or "Map & Coverage Explorer" in response.text


def test_realistic_gcov_filename_separates_bandwidth_mode_from_polarization_mode():
    svc = NisarCoverageService(search_client=lambda **kwargs: [])
    scene = "NISAR_L2_PR_GCOV_024_033_A_017_4005_DHDH_A_20260628T112725_20260628T112800_P05023_N_F_J_001"
    item = MockASFProduct({
        "sceneName": scene,
        "processingLevel": "GCOV",
        "startTime": "2026-06-28T11:27:25Z",
        "pathNumber": 33,
        "frameNumber": 17,
        "flightDirection": "ASCENDING",
        "beamModeType": None,
        "polarization": [],
        "rangeBandwidth": [40, 5],
        "sensor": "L-SAR",
    })
    acq = svc._normalize_product(item, "GCOV", "PROVISIONAL")
    assert acq.beam_mode.startswith("4005")
    assert acq.bandwidth == "40+5 MHz"
    assert acq.polarizations == ["HH", "HV"]


def test_partial_subquery_failure_returns_partial_results_with_warnings(monkeypatch):
    """Verifies that if one sub-query fails/times out, other completed results are preserved."""
    def partial_mock_search(**kwargs):
        pl = kwargs.get("processingLevel")
        mat = kwargs.get("dataMaturity")
        if pl == "GCOV" and mat == "PROVISIONAL":
            return [make_sample_gcov("GCOV_P_001", "2026-08-01T10:15:00Z")]
        elif pl == "GUNW":
            raise TimeoutError("Simulated ASF sub-query timeout for GUNW")
        return []

    monkeypatch.setattr(coverage_service, "search_client", partial_mock_search)
    coverage_service._cache.clear()

    payload = {
        "geometry": {"type": "Point", "coordinates": [-25.1, 15.1]},
        "requested_products": ["GCOV", "GUNW", "GOFF"]
    }
    response = client.post("/api/coverage/search", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["search_status"] == "AVAILABLE"
    assert data["products"]["GCOV"]["total_count"] == 1
    assert any("GUNW" in w for w in data["warnings"])

