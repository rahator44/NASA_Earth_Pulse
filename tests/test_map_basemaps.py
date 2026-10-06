"""Regression checks that every MapLibre instance shares safe basemaps."""
import re

import pytest
from fastapi.testclient import TestClient

from app.config import get_mapbox_public_token
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_all_map_routes_render(client):
    assert client.get("/map").status_code == 200
    assert client.get("/dashboard").status_code == 200
    assert client.get("/event/event_synth_001").status_code == 200


def test_shared_basemap_config_and_no_active_carto_urls(client):
    basemaps_js = client.get("/static/js/map_basemaps.js").text
    app_root = __import__("pathlib").Path(__file__).parents[1] / "app"
    active_files = [*app_root.rglob("*.js"), *app_root.rglob("*.html")]
    active_text = "\n".join(path.read_text() for path in active_files)

    assert not re.search(r"carto|cartocdn|basemaps\.cartocdn|dark_all|light_all", active_text, re.I)
    assert "https://tile.openstreetmap.org/{z}/{x}/{y}.png" in basemaps_js
    assert "https://api.mapbox.com/v4/mapbox.satellite/" in basemaps_js
    assert "mapbox-satellite" in basemaps_js and "satellite-basemap" in basemaps_js
    assert "© Mapbox © OpenStreetMap contributors" in basemaps_js
    assert "© OpenStreetMap contributors" in basemaps_js
    assert "return publicToken ? 'satellite' : 'streets';" in basemaps_js
    assert "setMode(map, 'streets')" in basemaps_js


def test_absent_or_secret_token_defaults_to_streets_and_is_not_exposed(client, monkeypatch):
    monkeypatch.delenv("MAPBOX_PUBLIC_TOKEN", raising=False)
    assert get_mapbox_public_token() == ""
    response = client.get("/map")
    assert response.status_code == 200
    assert "MAPBOX_PUBLIC_TOKEN = \"\"" in response.text
    assert "Satellite basemap requires Mapbox configuration." in response.text
    satellite_button = response.text.split('id="basemap-satellite"', 1)[1].split("</button>", 1)[0]
    assert "disabled" in satellite_button

    secret = "sk.this-is-a-secret-token-value-123456"
    monkeypatch.setenv("MAPBOX_PUBLIC_TOKEN", secret)
    assert get_mapbox_public_token() == ""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert secret not in response.text
    assert "mapbox-satellite" not in response.text


def test_public_pk_token_enables_satellite_and_is_exposed_only_on_map_pages(client, monkeypatch):
    public_token = "pk.test-public-token-value-1234567890"
    monkeypatch.setenv("MAPBOX_PUBLIC_TOKEN", public_token)
    assert get_mapbox_public_token() == public_token

    map_response = client.get("/map")
    dashboard_response = client.get("/dashboard")
    event_response = client.get("/event/event_synth_001")
    assert map_response.status_code == dashboard_response.status_code == event_response.status_code == 200
    assert f'MAPBOX_PUBLIC_TOKEN = "{public_token}"' in map_response.text
    assert "window.NisarBasemaps.canUseSatellite()" in map_response.text or "basemap-satellite" in map_response.text
    assert f'MAPBOX_PUBLIC_TOKEN = "{public_token}"' in dashboard_response.text
    assert f'MAPBOX_PUBLIC_TOKEN = "{public_token}"' in event_response.text
    satellite_button = map_response.text.split('id="basemap-satellite"', 1)[1].split("</button>", 1)[0]
    assert "disabled" not in satellite_button


def test_dashboard_and_event_detail_use_shared_provider(client):
    dashboard_js = client.get("/static/js/dashboard_map.js").text
    event_template = client.get("/event/event_synth_001").text
    assert "window.NisarBasemaps.createStyle()" in dashboard_js
    assert "window.NisarBasemaps.bindFallback(map)" in dashboard_js
    assert "window.NisarBasemaps.createStyle()" in event_template
    assert "window.NisarBasemaps.bindFallback(map)" in event_template
    assert "analyzed-aois-fill" in dashboard_js
    assert "aoi-fill" in event_template and "regions-fill" in event_template
