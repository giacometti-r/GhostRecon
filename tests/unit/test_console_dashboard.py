from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from dash import html
from fastapi.testclient import TestClient

from ghostrecon.common.config import Settings
from ghostrecon.console.api import (
    ConsoleApiClient,
    ConsoleApiError,
    any_stale,
    degraded_dependencies,
    idempotency_key,
)
from ghostrecon.console.callbacks import perform_dashboard_action
from ghostrecon.console.layouts import render_navigation, render_page
from ghostrecon.service_apps.factory import build_app

NOW = datetime(2026, 7, 7, tzinfo=UTC).isoformat()


def _metadata(stale: bool = False) -> dict[str, Any]:
    return {
        "generated_at": NOW,
        "watermarks": {"projection_generated_at": NOW},
        "projection_version": "reporting.v1.query",
        "stale": stale,
        "degraded_dependencies": ["source-a"] if stale else [],
    }


@dataclass
class RecordedRequest:
    method: str
    url: str
    params: dict[str, Any] | None
    json: dict[str, Any] | None
    headers: dict[str, str]


class FakeHttpClient:
    responses: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}
    requests: list[RecordedRequest] = []
    fail_timeout = False

    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        if self.fail_timeout:
            raise httpx.TimeoutException("timeout")
        self.requests.append(RecordedRequest(method, url, params, json, headers or {}))
        path = url.removeprefix("http://gateway.test")
        status, payload = self.responses.get((method, path), (200, {}))
        return httpx.Response(status, json=payload)

    def close(self) -> None:
        return None


def _client() -> ConsoleApiClient:
    FakeHttpClient.responses = {}
    FakeHttpClient.requests = []
    FakeHttpClient.fail_timeout = False
    return ConsoleApiClient(
        base_url="http://gateway.test/",
        timeout_seconds=3,
        actor="analyst@example.com",
        role="analyst",
        client_factory=FakeHttpClient,
    )


def test_console_api_client_builds_urls_headers_and_errors() -> None:
    client = _client()
    FakeHttpClient.responses = {
        ("GET", "/v1/reporting/events"): (
            200,
            {"metadata": _metadata(stale=True), "events": []},
        )
    }

    payload = client.get("/v1/reporting/events", params={"limit": 1, "source": ""})

    request = FakeHttpClient.requests[0]
    assert request.url == "http://gateway.test/v1/reporting/events"
    assert request.params == {"limit": 1}
    assert request.headers["X-Actor"] == "analyst@example.com"
    assert request.headers["X-Operator-Role"] == "analyst"
    assert any_stale([payload]) is True
    assert degraded_dependencies([payload]) == ["source-a"]

    FakeHttpClient.responses = {("POST", "/v1/crm/exports"): (409, {"detail": "conflict"})}
    try:
        client.post("/v1/crm/exports", payload={}, idempotency_key="key-1")
    except ConsoleApiError as exc:
        assert exc.status_code == 409
        assert str(exc) == "conflict"
    else:
        raise AssertionError("expected ConsoleApiError")


def test_console_api_client_maps_timeout() -> None:
    client = _client()
    FakeHttpClient.fail_timeout = True

    try:
        client.get("/v1/reporting/events")
    except ConsoleApiError as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("expected timeout error")


def test_dashboard_idempotency_key_accepts_composite_target_parts() -> None:
    key = idempotency_key("manual-event", "Cyber Summit", "https://example.test/event")

    assert key.startswith("dashboard:manual-event:Cyber Summit:https://example.test/event:")


def test_console_service_renders_dash_and_preserves_existing_routes(monkeypatch) -> None:
    async def fake_review_candidates(**_kwargs):
        return []

    monkeypatch.setattr(
        "ghostrecon.service_apps.routers.list_review_candidates",
        fake_review_candidates,
    )

    client = TestClient(build_app(Settings(service_name="console-service")))

    home = client.get("/")
    health = client.get("/healthz")
    review = client.get("/v1/review/candidates")

    assert home.status_code == 200
    assert "GhostRecon Console" in home.text
    assert health.json()["service"] == "console-service"
    assert review.status_code == 200


def test_render_page_handles_empty_and_degraded_reporting_payload() -> None:
    client = _client()
    FakeHttpClient.responses = {
        ("GET", "/v1/reporting/events"): (
            200,
            {"metadata": _metadata(stale=True), "events": [], "next_cursor": None},
        )
    }

    page = render_page(
        "/events",
        "?country=US",
        "analyst@example.com",
        "analyst",
        Settings(service_name="console-service"),
        client=client,
    )

    assert isinstance(page, html.Div)
    rendered = str(page)
    assert "Stale reporting data" in rendered
    assert "No records match" in rendered


def test_render_page_humanizes_todo_views() -> None:
    client = _client()
    FakeHttpClient.responses = {
        ("GET", "/v1/reporting/kpis/catalog"): (
            200,
            {"metadata": _metadata(), "kpis": {"source_freshness": ["parse_yield"]}},
        ),
        ("GET", "/v1/reporting/source-health"): (200, {"metadata": _metadata(), "sources": []}),
        ("GET", "/v1/reporting/review-queue"): (200, {"metadata": _metadata(), "candidates": []}),
        ("GET", "/v1/reporting/crm-targets"): (200, {"metadata": _metadata(), "crm_targets": []}),
        ("GET", "/v1/reporting/meetings"): (200, {"metadata": _metadata(), "meetings": []}),
        ("GET", "/v1/reporting/events"): (
            200,
            {
                "metadata": _metadata(),
                "events": [
                    {
                        "id": "event-1",
                        "name": "Demo Event",
                        "country": "USA",
                        "latitude": 36.0908,
                        "longitude": -115.1761,
                        "street_address": "3950 Las Vegas Blvd S",
                        "city": "Las Vegas",
                        "confidence": 90,
                    }
                ],
            },
        ),
        ("GET", "/v1/reporting/events/event-1"): (
            200,
            {
                "metadata": _metadata(),
                "event": {
                    "id": "event-1",
                    "topics": ["security"],
                    "version": 1,
                    "event_format": "in-person",
                },
            },
        ),
        ("GET", "/v1/intelligence/events/event-1/participants"): (
            200,
            {"participants": [{"id": "participant-1", "published_name": "Ada Analyst"}]},
        ),
        ("GET", "/v1/enrichment/contact-candidates"): (200, {"candidates": []}),
        ("GET", "/v1/reporting/incidents"): (
            200,
            {
                "metadata": _metadata(),
                "incidents": [{"id": "incident-1", "version": 1, "status": "candidate"}],
            },
        ),
        ("GET", "/v1/reporting/watch-targets"): (
            200,
            {
                "metadata": _metadata(),
                "watch_targets": [
                    {
                        "id": "watch-1",
                        "display_name": "Example Corp",
                        "owner": "analyst@example.com",
                        "enabled": True,
                        "monitoring_enabled": True,
                        "monitoring_status": "completed",
                        "version": 1,
                    }
                ],
            },
        ),
        ("GET", "/v1/reporting/watch-targets/watch-1"): (
            200,
            {
                "metadata": _metadata(),
                "watch_target": {
                    "id": "watch-1",
                    "display_name": "Example Corp",
                    "owner": "analyst@example.com",
                    "enabled": True,
                    "monitoring_enabled": True,
                    "monitoring_status": "completed",
                    "monitoring_summary": {"result_count": 1},
                    "version": 1,
                },
            },
        ),
    }

    overview = str(
        render_page("/", "", "analyst@example.com", "analyst", Settings(), client=client)
    )
    events = str(
        render_page("/events", "", "analyst@example.com", "analyst", Settings(), client=client)
    )
    event_detail = str(
        render_page(
            "/events/event-1",
            "",
            "analyst@example.com",
            "analyst",
            Settings(),
            client=client,
        )
    )
    event_detail_reviewer = str(
        render_page(
            "/events/event-1",
            "",
            "reviewer@example.com",
            "governance_reviewer",
            Settings(),
            client=client,
        )
    )
    event_detail_admin = str(
        render_page(
            "/events/event-1",
            "",
            "admin@example.com",
            "administrator",
            Settings(),
            client=client,
        )
    )
    incidents = str(
        render_page("/incidents", "", "analyst@example.com", "analyst", Settings(), client=client)
    )
    watchlists = str(
        render_page("/watchlists", "", "analyst@example.com", "analyst", Settings(), client=client)
    )
    watchlist_detail = str(
        render_page(
            "/watchlists/watch-1",
            "",
            "analyst@example.com",
            "analyst",
            Settings(),
            client=client,
        )
    )

    assert "Source Freshness" in overview
    assert "Parse Yield" in overview
    assert "Event map" in events
    assert "Confidence" not in events
    assert "Add to Enrichment Queue" in event_detail
    assert "security" in event_detail
    assert "Projection" not in event_detail
    assert "Projection" in event_detail_reviewer
    assert "Projection" not in event_detail_admin
    assert "Incident Status" not in incidents
    assert "Add incident" in incidents
    assert "Example Corp" in watchlists
    assert "Target Type" not in watchlists
    assert "Canonical Target Key" not in watchlists
    assert "Watchlist Item" in watchlist_detail
    assert "Find Contact" in watchlist_detail


def test_render_navigation_marks_active_parent_route() -> None:
    links = render_navigation("/meetings/meeting-1")
    rendered_links = [str(link) for link in links]

    assert sum("nav-link active" in rendered for rendered in rendered_links) == 1
    active = next(rendered for rendered in rendered_links if "nav-link active" in rendered)
    assert "Meetings" in active
    assert "aria-current" in active


def test_render_page_shows_sequence_workflow_and_structured_meeting_prep() -> None:
    client = _client()
    FakeHttpClient.responses = {
        ("GET", "/v1/sequences/enrollments"): (
            200,
            {"enrollments": [{"id": "enroll-1", "sequence_id": "sequence-1"}]},
        ),
        ("GET", "/v1/sequences"): (
            200,
            {
                "sequences": [
                    {
                        "id": "sequence-1",
                        "name": "Multi-channel",
                        "owner_id": "demo-ae",
                        "channel": "email",
                        "status": "active",
                        "definition_version": 2,
                        "rate_limit_policy": {},
                        "steps": [
                            {
                                "id": "step-1",
                                "step_order": 1,
                                "channel": "email",
                                "delay_seconds": 0,
                                "subject_template": "Hi",
                                "requires_approval": True,
                            },
                            {
                                "id": "step-2",
                                "step_order": 2,
                                "channel": "call",
                                "delay_seconds": 86400,
                                "step_metadata": {"instructions": "Call security leader"},
                            },
                        ],
                    }
                ]
            },
        ),
        ("GET", "/v1/sequences/activities"): (
            200,
            {
                "activities": [
                    {
                        "id": "activity-1",
                        "contact_name": "Taylor Ng",
                        "account_name": "Example Industries",
                        "channel": "email",
                        "status": "pending_approval",
                        "step_order": 1,
                    }
                ]
            },
        ),
        ("GET", "/v1/sequences/crm-prospects"): (
            200,
            {
                "prospects": [
                    {
                        "provider_record_id": "demo-crm-prospect-taylor-ng",
                        "display_name": "Taylor Ng",
                        "email": "taylor.ng@example-industries.com",
                        "company_name": "Example Industries",
                    }
                ]
            },
        ),
        ("GET", "/v1/reporting/meetings/meeting-1"): (
            200,
            {
                "metadata": _metadata(),
                "meeting": {
                    "id": "meeting-1",
                    "subject": "Security discovery",
                    "status": "scheduled",
                    "prep_packet": {
                        "account_summary": "Example Industries has active incident intent.",
                        "stakeholder_map": [{"name": "Taylor Ng", "role": "VP Security"}],
                        "likely_security_priorities": ["identity response"],
                        "suggested_questions": ["Where does reporting slow down?"],
                        "risks": ["Validate current priorities."],
                        "source_snapshot": {"account_id": "account-1"},
                    },
                    "follow_up_tasks": [],
                },
            },
        ),
    }

    sequences = str(
        render_page(
            "/sequences",
            "",
            "analyst@example.com",
            "analyst",
            Settings(),
            client=client,
        )
    )
    definitions = str(
        render_page(
            "/sequences/definitions",
            "",
            "analyst@example.com",
            "analyst",
            Settings(),
            client=client,
        )
    )
    meeting = str(
        render_page(
            "/meetings/meeting-1",
            "",
            "analyst@example.com",
            "analyst",
            Settings(),
            client=client,
        )
    )

    assert "Sequence Definitions" in sequences
    assert "CRM prospect import" in sequences
    assert "Sequence activities" in sequences
    assert "Create sequence" in definitions
    assert "Multi-channel" in definitions
    assert "Account context" in meeting
    assert "Recommended talk tracks" in meeting
    assert "Taylor Ng" in meeting


def test_render_page_surfaces_gateway_error_path_and_status() -> None:
    client = _client()
    FakeHttpClient.responses = {
        ("GET", "/v1/reporting/events"): (
            503,
            {"detail": "reporting database unavailable"},
        )
    }

    page = render_page(
        "/events",
        "",
        "analyst@example.com",
        "analyst",
        Settings(service_name="console-service"),
        client=client,
    )

    rendered = str(page)
    assert "reporting database unavailable" in rendered
    assert "Endpoint: /v1/reporting/events" in rendered
    assert "Status: 503" in rendered


def test_dashboard_actions_send_expected_gateway_mutations() -> None:
    client = _client()
    FakeHttpClient.responses = {
        ("POST", "/v1/review/candidates/review-1/approve"): (200, {"id": "decision-1"}),
        ("POST", "/v1/review/candidates/bulk-decision"): (200, {"decisions": []}),
        ("POST", "/v1/crm/exports"): (200, {"id": "batch-1"}),
        ("POST", "/v1/crm/exports/batch-1/retry-failed"): (200, {"id": "batch-1"}),
        ("POST", "/v1/intelligence/incidents/incident-1/promote-to-watchlist"): (
            200,
            {"id": "watch-1"},
        ),
        ("POST", "/v1/governance/incidents/incident-1/revert"): (
            200,
            {"id": "decision-2"},
        ),
        ("PATCH", "/v1/intelligence/watch-targets/watch-1"): (200, {"id": "watch-1"}),
        ("POST", "/v1/enrichment/watch-targets/watch-1/find-contact"): (
            200,
            {"contact_candidates": [{"id": "candidate-1"}]},
        ),
        ("POST", "/v1/enrichment/contact-candidates/candidate-1/discover-domain"): (
            200,
            {"discovered_domain": "example.com"},
        ),
        ("POST", "/v1/sequences/enrollments/enroll-1/pause"): (200, {"id": "enroll-1"}),
        ("POST", "/v1/sequences/activities/activity-1/approve-email"): (
            200,
            {"id": "activity-1"},
        ),
        ("POST", "/v1/sequences/activities/activity-2/complete"): (
            200,
            {"id": "activity-2"},
        ),
        ("POST", "/v1/sequences/activities/activity-3/schedule-meeting"): (
            200,
            {"id": "activity-3"},
        ),
        ("POST", "/v1/enrichment/event-participants/participant-1/enrich-target"): (
            200,
            {"verified_email": "ada@example.com"},
        ),
        ("POST", "/v1/meetings/meeting-1/prep-packet"): (200, {"id": "meeting-1"}),
        ("POST", "/v1/meetings/meeting-1/outcome"): (200, {"id": "meeting-1"}),
        ("POST", "/v1/meetings/meeting-1/cancel"): (200, {"id": "meeting-1"}),
        ("POST", "/v1/meetings/meeting-1/retry-sync"): (200, {"id": "meeting-1"}),
    }
    settings = Settings(service_name="console-service")

    actions = [
        {
            "kind": "review",
            "action": "approve",
            "target_id": "review-1",
            "version": 2,
            "policy_hash": "hash",
            "enabled": None,
        },
        {
            "kind": "bulk-review",
            "action": "reject",
            "target_id": "review-1,review-2",
            "version": {"review-1": 2, "review-2": 3},
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "crm-export",
            "action": "start",
            "target_id": "crm-target-1",
            "version": 1,
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "crm-retry",
            "action": "retry",
            "target_id": "batch-1",
            "version": None,
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "incident",
            "action": "promote",
            "target_id": "incident-1",
            "version": 1,
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "incident",
            "action": "revert",
            "target_id": "incident-1",
            "version": 2,
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "watch",
            "action": "toggle",
            "target_id": "watch-1",
            "version": 4,
            "policy_hash": None,
            "enabled": False,
        },
        {
            "kind": "watch",
            "action": "find-contact",
            "target_id": "watch-1",
            "version": None,
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "contact-candidate",
            "action": "discover-domain",
            "target_id": "candidate-1",
            "version": None,
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "sequence",
            "action": "pause",
            "target_id": "enroll-1",
            "version": None,
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "sequence-activity",
            "action": "approve-email",
            "target_id": "activity-1",
            "version": None,
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "sequence-activity",
            "action": "complete",
            "target_id": "activity-2",
            "version": None,
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "sequence-activity",
            "action": "schedule-meeting",
            "target_id": "activity-3",
            "version": None,
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "meeting",
            "action": "prep",
            "target_id": "meeting-1",
            "version": None,
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "meeting",
            "action": "outcome",
            "target_id": "meeting-1",
            "version": None,
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "meeting",
            "action": "cancel",
            "target_id": "meeting-1",
            "version": None,
            "policy_hash": None,
            "enabled": None,
        },
        {
            "kind": "meeting",
            "action": "retry-sync",
            "target_id": "meeting-1",
            "version": None,
            "policy_hash": None,
            "enabled": None,
        },
    ]

    for action in actions:
        perform_dashboard_action(
            action,
            actor="analyst@example.com",
            role="analyst",
            settings=settings,
            client=client,
        )

    perform_dashboard_action(
        {
            "kind": "event-participant",
            "action": "enrich",
            "target_id": "participant-1",
            "version": None,
            "policy_hash": None,
            "enabled": None,
        },
        actor="analyst@example.com",
        role="analyst",
        settings=settings,
        client=client,
        extra_payload={"domain": "example.com"},
    )
    perform_dashboard_action(
        {
            "kind": "sequence",
            "action": "pause",
            "target_id": "enroll-1",
            "version": None,
            "policy_hash": None,
            "enabled": None,
        },
        actor="analyst@example.com",
        role="analyst",
        settings=settings,
        client=client,
        extra_payload={"reason": "Need legal review."},
    )

    paths = [request.url.removeprefix("http://gateway.test") for request in FakeHttpClient.requests]
    assert "/v1/crm/exports" in paths
    assert "/v1/review/candidates/bulk-decision" in paths
    assert "/v1/sequences/enrollments/enroll-1/pause" in paths
    assert "/v1/sequences/activities/activity-1/approve-email" in paths
    assert "/v1/sequences/activities/activity-2/complete" in paths
    assert "/v1/sequences/activities/activity-3/schedule-meeting" in paths
    assert "/v1/enrichment/watch-targets/watch-1/find-contact" in paths
    assert "/v1/enrichment/contact-candidates/candidate-1/discover-domain" in paths
    assert "/v1/enrichment/event-participants/participant-1/enrich-target" in paths
    assert "/v1/governance/incidents/incident-1/revert" in paths
    promote_payloads = [
        request.json
        for request in FakeHttpClient.requests
        if request.url.endswith("/v1/intelligence/incidents/incident-1/promote-to-watchlist")
    ]
    assert promote_payloads[-1] == {"version": 1}
    pause_payloads = [
        request.json
        for request in FakeHttpClient.requests
        if request.url.endswith("/v1/sequences/enrollments/enroll-1/pause")
    ]
    assert pause_payloads[-1] == {"reason": "Need legal review."}
    assert FakeHttpClient.requests[0].headers["Idempotency-Key"].startswith("dashboard:")


def test_viewer_cannot_mutate_from_dashboard() -> None:
    try:
        perform_dashboard_action(
            {
                "kind": "crm-export",
                "action": "start",
                "target_id": "crm-target-1",
                "version": None,
                "policy_hash": None,
                "enabled": None,
            },
            actor="viewer@example.com",
            role="viewer",
            settings=Settings(service_name="console-service"),
            client=_client(),
        )
    except ConsoleApiError as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("viewer mutation should fail closed")
