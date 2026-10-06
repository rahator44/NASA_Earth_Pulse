"""
Home Feed tests for NISAR Surface Change Explorer.
Step 4: Home / Change Feed integration, editorial layout, and presentation safety.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.models import Domain
from app.utils.presentation import format_domain_label, get_event_card_views


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_home_page_status_200(client):
    """1. GET / returns 200 OK."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Observe how Earth's surface changes." in response.text


def test_synthetic_events_appear(client):
    """2. Synthetic demo events appear when fixture events exist."""
    response = client.get("/")
    assert response.status_code == 200
    # Verifies seeded event titles and IDs appear
    assert "event_synth_001" in response.text
    assert "Synthetic Wetland Fluctuation Event" in response.text


def test_synthetic_fixture_badge_present(client):
    """3. Synthetic fixture badge and disclaimer appear for synthetic events."""
    response = client.get("/")
    assert "DEMO FIXTURE" in response.text
    assert "Synthetic development fixture — not an Earth observation result." in response.text


def test_event_links_use_event_id(client):
    """4. Event links use /event/{event_id} correctly."""
    response = client.get("/")
    assert "/event/event_synth_001" in response.text
    assert "/event/event_synth_002" in response.text
    assert "/event/event_synth_003" in response.text
    assert "/event/event_synth_004" in response.text


def test_unknown_change_unidentified_cause(client):
    """5. unknown_change renders neutral unidentified-cause language."""
    response = client.get("/")
    assert "Unusual radar change detected" in response.text or "Cause not identified" in response.text or "Ambiguous" in response.text


def test_insufficient_data_not_no_change(client):
    """6. insufficient_data does NOT render as No Change."""
    response = client.get("/")
    # Check that insufficient data text is present and explicitly distinguished
    assert "INSUFFICIENT DATA" in response.text
    assert "Not enough usable data to determine surface change" in response.text or "partial scan" in response.text.lower()


def test_no_change_separate_from_insufficient_data(client):
    """7. no_change renders separately from insufficient_data with surface stability wording."""
    response = client.get("/")
    assert "NO CHANGE" in response.text
    assert "No significant surface change was detected in the analyzed observations" in response.text or "stability" in response.text.lower()


def test_domain_labels_presentation_safe(client):
    """8. Domain labels are presentation-safe; wildfire does NOT render as 'WILDFIRE DETECTED'."""
    assert format_domain_label(Domain.WILDFIRE) == "Vegetation Disturbance"
    assert format_domain_label(Domain.FLOOD_WETLAND) == "Flood / Wetland"
    assert format_domain_label(Domain.GLACIER) == "Glacier Change"
    assert format_domain_label(Domain.DEFORMATION) == "Ground Deformation"
    assert format_domain_label(Domain.UNCLASSIFIED) == "Unclassified Change"

    response = client.get("/")
    assert "Vegetation Disturbance" in response.text
    assert "WILDFIRE DETECTED" not in response.text


def test_empty_state_renders_when_no_events(client):
    """9. Empty-state component renders when event list is empty."""
    with patch("app.services.demo_data.demo_service.get_events", return_value=[]):
        response = client.get("/")
        assert response.status_code == 200
        assert "NO ANALYZED CHANGES AVAILABLE" in response.text
        assert "No processed surface-change analyses are available in the current demo dataset." in response.text
        assert "Explore NISAR Coverage" in response.text
