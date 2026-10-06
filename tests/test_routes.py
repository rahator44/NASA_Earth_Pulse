"""
Route verification and visual design system tests for NISAR Surface Change Explorer.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "NISAR" in data["app"]


def test_home_route(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "NISAR Surface Change Explorer" in response.text
    assert "NASA Space Apps Challenge" in response.text or "NASA SPACE APPS CHALLENGE" in response.text
    # Check media card and demo fixture indicators are present
    assert "DEMO FIXTURE" in response.text or "SYNTHETIC DEMO" in response.text
    assert "media-card" in response.text


def test_map_route(client):
    response = client.get("/map")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Map &amp; Coverage Explorer" in response.text or "Map & Coverage Explorer" in response.text
    assert 'id="map"' in response.text
    assert "maplibre-gl" in response.text
    # Verify Area Inspector layout shell is present
    assert "AREA INSPECTOR" in response.text
    assert "No Area Selected" in response.text


def test_event_detail_route(client):
    response = client.get("/event/event_synth_001")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "event_synth_001" in response.text
    assert "Synthetic Wetland Fluctuation Event" in response.text


def test_copilot_route(client):
    response = client.get("/copilot")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Earth Copilot" in response.text
    assert "Open Copilot from an event record to load its stored analysis context" in response.text


def test_lab_route(client):
    response = client.get("/lab/demo")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Scientist Image Lab" in response.text
    assert "demo" in response.text
    assert "DISPLAY CONTROLS" in response.text


def test_dashboard_route(client):
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Situation Dashboard" in response.text
    # Verify neutral observation language: "tactical" must NOT appear
    assert "tactical" not in response.text.lower()
    assert "Review analyzed surface-change records and their evidence" in response.text


def test_methods_route(client):
    response = client.get("/methods")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Methods &amp; Scientific Transparency" in response.text or "Methods & Scientific Transparency" in response.text


def test_settings_route(client):
    response = client.get("/settings")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Settings" in response.text


def test_static_assets_serve(client):
    css_res = client.get("/static/css/app.css")
    assert css_res.status_code == 200
    assert "--color-accent" in css_res.text
    assert "--color-surface-elevated" in css_res.text
    assert "--color-state-no-change" in css_res.text
    assert "--color-state-change" in css_res.text
    assert "--color-state-strong" in css_res.text
    assert "--color-state-unknown" in css_res.text
    assert "--color-state-insufficient" in css_res.text
    assert ".media-card" in css_res.text
    assert ".empty-state" in css_res.text
    assert ".skeleton" in css_res.text

    js_res = client.get("/static/js/app.js")
    assert js_res.status_code == 200

    nav_js = client.get("/static/js/navigation.js")
    assert nav_js.status_code == 200

    map_js = client.get("/static/js/map.js")
    assert map_js.status_code == 200


def test_convenience_redirects(client):
    # /lab without analysis_id redirects to showcase analysis
    res_lab = client.get("/lab", follow_redirects=False)
    assert res_lab.status_code == 307
    assert res_lab.headers["location"] == "/lab/real_flood_001"

    # /event and /events redirect to /dashboard
    res_event = client.get("/event", follow_redirects=False)
    assert res_event.status_code == 307
    assert res_event.headers["location"] == "/dashboard"

    res_events = client.get("/events", follow_redirects=False)
    assert res_events.status_code == 307
    assert res_events.headers["location"] == "/dashboard"

    # /setting redirects to /settings
    res_setting = client.get("/setting", follow_redirects=False)
    assert res_setting.status_code == 307
    assert res_setting.headers["location"] == "/settings"


def test_copilot_without_event_lists_available_records(client):
    response = client.get("/copilot")
    assert response.status_code == 200
    assert "real_flood_001" in response.text
    assert "Lake Henderson / Atchafalaya Basin" in response.text
    assert "REAL NISAR" in response.text

