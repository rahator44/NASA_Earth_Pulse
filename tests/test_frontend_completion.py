import asyncio
import httpx

from app.main import app


def get(path):
    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(path)
    return asyncio.run(request())


def test_copilot_context_is_stored_record_grounded():
    response = get("/copilot?event=event_synth_001")
    assert response.status_code == 200
    assert "ACTIVE CONTEXT" in response.text
    assert "Synthetic Wetland Fluctuation Event" in response.text
    assert "Should I evacuate?" in response.text
    assert "Follow local authorities and official emergency alert services." in response.text


def test_invalid_copilot_event_has_no_fabricated_analysis():
    response = get("/copilot?event=missing-event")
    assert response.status_code == 200
    assert "No computed analysis exists for this request." in response.text
    assert "ACTIVE CONTEXT" in response.text


def test_settings_exposes_local_public_and_scientist_controls():
    response = get("/settings")
    assert response.status_code == 200
    assert 'data-mode-option="public"' in response.text
    assert 'data-mode-option="scientist"' in response.text
    assert 'data-pref="reducedMotion"' in response.text
    assert 'data-pref="showFootprints"' in response.text


def test_real_and_synthetic_records_are_distinct_and_footer_disclaimer_renders():
    response = get("/")
    assert response.status_code == 200
    assert "REAL NISAR ANALYSIS" in response.text
    assert "DEMONSTRATION OBSERVATIONS" in response.text
    assert "DEMO FIXTURE" in response.text
    assert "does not predict disasters or issue emergency instructions" in response.text


def test_global_navigation_contains_required_routes():
    response = get("/")
    for href in ('href="/"', 'href="/map"', 'href="/dashboard"',
                 'href="/lab/real_flood_001"', 'href="/methods"',
                 'href="/copilot"', 'href="/settings"'):
        assert href in response.text


def test_required_routes_and_styled_invalid_records():
    paths = []
    async def request_routes():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for path in ("/", "/map", "/dashboard", "/methods", "/settings", "/copilot", "/health",
                         "/event/event_synth_001", "/lab/real_flood_001", "/event/missing-event", "/lab/missing-analysis"):
                response = await client.get(path)
                paths.append((path, response.status_code, response.text))
    asyncio.run(request_routes())
    expected = {"/": 200, "/map": 200, "/dashboard": 200, "/methods": 200,
                "/settings": 200, "/copilot": 200, "/health": 200,
                "/event/event_synth_001": 200, "/lab/real_flood_001": 200,
                "/event/missing-event": 404, "/lab/missing-analysis": 404}
    for path, status, _ in paths:
        assert status == expected[path]
    assert "NOT FOUND" in dict((path, body) for path, _, body in paths)["/event/missing-event"]
    assert "NOT FOUND" in dict((path, body) for path, _, body in paths)["/lab/missing-analysis"]
