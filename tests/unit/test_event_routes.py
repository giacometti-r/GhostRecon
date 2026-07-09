from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from ghostrecon.common.config import Settings
from ghostrecon.service_apps import routers
from ghostrecon.service_apps.factory import build_app


def _event():
    now = datetime(2026, 7, 3, tzinfo=UTC)
    return SimpleNamespace(
        id="event-1",
        name="DEF CON 34",
        event_series_key="def-con",
        external_id="defcon-34",
        canonical_url="https://defcon.org/",
        original_start="2026-08-06T09:00:00",
        original_end=None,
        source_timezone="America/Los_Angeles",
        iana_timezone="America/Los_Angeles",
        timezone_status="resolved",
        starts_at_utc=now,
        ends_at_utc=None,
        event_format="physical",
        venue_name="Convention Center",
        street_address="3950 Las Vegas Blvd S",
        city="Las Vegas",
        region="NV",
        postcode="89119",
        country="US",
        virtual_url=None,
        latitude=36.0908,
        longitude=-115.1761,
        geocode_status="resolved",
        geocode_provider="source",
        geocode_display_name="Mandalay Bay, Las Vegas",
        geocoded_at=now,
        topics=["security"],
        organizers=[{"name": "DEF CON"}],
        confidence=90,
        canonical_state="canonical",
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
        version=1,
        created_at=now,
        updated_at=now,
    )


def _participant():
    now = datetime(2026, 7, 3, tzinfo=UTC)
    return SimpleNamespace(
        id="participant-1",
        cyber_event_id="event-1",
        source_definition_id="source-1",
        source_item_id="raw-1",
        source_participant_id="speaker-1",
        published_name="Ada Lovelace",
        organization="Example Security",
        published_role="Researcher",
        participant_type="speaker",
        profile_url="https://example.com/ada",
        reuse_state="unknown",
        reuse_evidence={},
        contact_extraction_allowed=False,
        crm_export_allowed=False,
        resolution_confidence=80,
        created_at=now,
        updated_at=now,
    )


def test_event_intelligence_routes_return_events_and_policy_gated_participants(monkeypatch) -> None:
    async def fake_list_events(**kwargs):
        return [_event()]

    async def fake_get_event(event_id, settings=None):
        return _event()

    async def fake_list_participants(**kwargs):
        return [_participant()]

    monkeypatch.setattr(routers, "list_events", fake_list_events)
    monkeypatch.setattr(routers, "get_event", fake_get_event)
    monkeypatch.setattr(routers, "list_participants", fake_list_participants)
    monkeypatch.setattr(routers, "create_manual_event", fake_get_event)

    app = build_app(Settings(service_name="event-intelligence-service"))
    client = TestClient(app)

    events = client.get("/v1/intelligence/events").json()["events"]
    participants = client.get("/v1/intelligence/events/event-1/participants").json()["participants"]

    assert events[0]["event_series_key"] == "def-con"
    assert events[0]["event_format"] == "in-person"
    assert events[0]["source_item_ids"] == ["raw-1"]
    assert participants[0]["reuse_state"] == "unknown"
    assert participants[0]["contact_extraction_allowed"] is False
    assert participants[0]["crm_export_allowed"] is False


def test_manual_event_route_uses_additive_create_contract(monkeypatch) -> None:
    async def fake_create_manual_event(request, **kwargs):
        assert request.name == "Manual Event"
        assert request.event_format.value == "online"
        assert kwargs["actor"] == "analyst@example.com"
        return _event()

    monkeypatch.setattr(routers, "create_manual_event", fake_create_manual_event)

    client = TestClient(build_app(Settings(service_name="event-intelligence-service")))
    response = client.post(
        "/v1/intelligence/events/manual",
        headers={"Idempotency-Key": "manual-event-1", "X-Actor": "analyst@example.com"},
        json={
            "name": "Manual Event",
            "canonical_url": "https://example.com/manual-event",
            "starts_at_utc": "2026-07-03T12:00:00Z",
            "event_format": "virtual",
            "virtual_url": "https://example.com/manual-event/join",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == "event-1"


def test_event_patch_route_uses_versioned_update_contract(monkeypatch) -> None:
    async def fake_update_event(event_id, request, **kwargs):
        assert event_id == "event-1"
        assert request.version == 1
        assert request.event_format.value == "in-person"
        assert kwargs["actor"] == "analyst@example.com"
        return _event()

    monkeypatch.setattr(routers, "update_event", fake_update_event)

    client = TestClient(build_app(Settings(service_name="event-intelligence-service")))
    response = client.patch(
        "/v1/intelligence/events/event-1",
        headers={"Idempotency-Key": "event-edit-1", "X-Actor": "analyst@example.com"},
        json={"version": 1, "event_format": "physical", "street_address": "Demo Way 42"},
    )

    assert response.status_code == 200
    assert response.json()["event_format"] == "in-person"
