"""Focused tests for map location search and the OSM basemap wiring."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.location_search import LocationSearchService, location_search_service


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_map_and_coordinate_search(client):
    assert client.get("/map").status_code == 200
    response = client.get("/api/locations/search", params={"q": "23.8103, 90.4125"})
    assert response.status_code == 200
    assert response.json()["results"] == [{
        "name": "23.8103, 90.4125", "lat": 23.8103, "lon": 90.4125, "source": "coordinates"
    }]


@pytest.mark.parametrize("query", ["90.0001, 0", "0, 180.0001"])
def test_coordinate_search_rejects_out_of_range_values(client, query):
    response = client.get("/api/locations/search", params={"q": query})
    assert response.status_code == 422


def test_text_search_normalizes_caps_and_caches(client, monkeypatch):
    service = location_search_service
    service._cache.clear()
    service._last_request_at = 0
    calls = []

    async def mocked_search(query):
        calls.append(query)
        return [
            {"name": f"Place {i}", "lat": 1.0, "lon": 2.0, "source": "nominatim"}
            for i in range(7)
        ]

    monkeypatch.setattr(service, "_request_nominatim", mocked_search)
    first = client.get("/api/locations/search", params={"q": "Dhaka"})
    second = client.get("/api/locations/search", params={"q": "  DHAKA  "})
    assert first.status_code == second.status_code == 200
    assert len(first.json()["results"]) == 5
    assert first.json()["results"][0]["source"] == "nominatim"
    assert len(calls) == 1


def test_geocoder_failure_is_safe(client, monkeypatch):
    service = location_search_service
    service._cache.clear()
    service._last_request_at = 0

    async def broken_search(_query):
        raise RuntimeError("private provider detail")

    monkeypatch.setattr(service, "_request_nominatim", broken_search)
    response = client.get("/api/locations/search", params={"q": "Singapore"})
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Place search is temporarily unavailable. You can still enter coordinates "
        "or select an area directly on the map."
    )
    assert "private provider detail" not in response.text


def test_location_search_service_coordinate_path_does_not_call_geocoder(monkeypatch):
    service = LocationSearchService()

    async def should_not_run(_query):
        raise AssertionError("coordinate query should not reach Nominatim")

    monkeypatch.setattr(service, "_request_nominatim", should_not_run)
    result = asyncio.run(service.search("-90, 180"))
    assert result[0]["source"] == "coordinates"


def test_nominatim_payload_is_normalized_and_limited(monkeypatch):
    requests = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return [
                {"display_name": f"Place {i}, Country", "lat": str(10 + i), "lon": "20"}
                for i in range(8)
            ]

    class FakeAsyncClient:
        def __init__(self, *, timeout, headers):
            assert timeout == 10.0
            assert headers["User-Agent"] == "NISAR-Surface-Change-Explorer-SpaceApps/1.0"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, url, *, params):
            requests.append((url, params))
            return FakeResponse()

    monkeypatch.setattr("app.services.location_search.httpx.AsyncClient", FakeAsyncClient)
    results = asyncio.run(LocationSearchService()._request_nominatim("Singapore"))
    assert len(results) == 5
    assert results[0] == {
        "name": "Place 0, Country", "lat": 10.0, "lon": 20.0, "source": "nominatim"
    }
    assert requests[0][1] == {"q": "Singapore", "format": "jsonv2", "limit": 5}


def test_map_template_and_scripts_keep_basemap_controls_and_separate_layers(client):
    html = client.get("/map").text
    js = client.get("/static/js/map.js").text
    basemaps_js = client.get("/static/js/map_basemaps.js").text
    css = client.get("/static/css/app.css").text
    selection_js = client.get("/static/js/map_selection.js").text

    assert "https://tile.openstreetmap.org/{z}/{x}/{y}.png" in basemaps_js
    assert "© OpenStreetMap contributors" in basemaps_js
    assert "type: 'raster'" in basemaps_js and "tileSize: 256" in basemaps_js and "maxzoom: 19" in basemaps_js
    assert "const OSM_LAYER_ID = 'osm-basemap-layer'" in basemaps_js and "source: OSM_SOURCE_ID" in basemaps_js
    assert "layout: { visibility: 'visible' }" in basemaps_js
    assert "Keep OSM visible underneath satellite" in basemaps_js
    assert "style: window.NisarBasemaps.createStyle()" in js
    assert "Satellite basemap unavailable — using OpenStreetMap." in client.get("/static/js/map_basemaps.js").text
    assert "map.on('load', async () =>" in js and "map.resize();" in js
    assert 'id="map"' in html and "min-height: 650px" in css
    assert 'id="basemap-satellite"' in html and 'id="basemap-streets"' in html
    assert "map.on('error'" in js
    assert "maplibre-gl@4.7.1/dist/maplibre-gl.js" in html
    assert "maplibre-gl@4.7.1/dist/maplibre-gl.css" in html
    assert "NavigationControl" in js and "showCompass: true" in js
    assert "ScaleControl" in js
    assert "basemap-satellite" in html and "basemap-streets" in html
    assert "OpenStreetMap" in html
    assert "real-analysis-aois" in js and "real-change-regions" in js
    assert "synthetic-aois" in js and "synthetic-change-regions" in js
    assert "layer-toggle-synthetic-aois" in html and "layer-toggle-synthetic-changes" in html
    assert "nisar-footprints" in js
    assert "user-selection" in selection_js
    assert "handleClickPoint" in selection_js
    assert "handleClickPoint" in js
    assert "api.openstreetmap.org" not in js
    assert "api.mapbox.com" not in js.lower()
