"""
Tests for live auto-reload and server heartbeat endpoints.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_status_heartbeat_returns_online():
    """Validates GET /api/system/status-heartbeat returns valid session and status."""
    response = client.get("/api/system/status-heartbeat")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "sessionId" in data
    assert "pid" in data
    assert "uptime" in data


def test_live_reload_stream_handshake():
    """Validates SSE stream connection on GET /api/system/live-reload."""
    response = client.get("/api/system/live-reload?once=true")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert "connected" in response.text
    assert "sessionId" in response.text
