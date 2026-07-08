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
        self.requests.append(
            RecordedRequest(method, url, params, json, headers or {})
        )
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


def test_render_navigation_marks_active_parent_route() -> None:
    links = render_navigation("/meetings/meeting-1")
    rendered_links = [str(link) for link in links]

    assert sum("nav-link active" in rendered for rendered in rendered_links) == 1
    active = next(rendered for rendered in rendered_links if "nav-link active" in rendered)
    assert "Meetings" in active
    assert "aria-current" in active


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
        ("PATCH", "/v1/intelligence/watch-targets/watch-1"): (200, {"id": "watch-1"}),
        ("POST", "/v1/sequences/enrollments/enroll-1/pause"): (200, {"id": "enroll-1"}),
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
            "version": None,
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
            "kind": "sequence",
            "action": "pause",
            "target_id": "enroll-1",
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

    paths = [request.url.removeprefix("http://gateway.test") for request in FakeHttpClient.requests]
    assert "/v1/crm/exports" in paths
    assert "/v1/review/candidates/bulk-decision" in paths
    assert "/v1/sequences/enrollments/enroll-1/pause" in paths
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
