from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, HTTPException, Request

from ghostrecon.common.config import Settings
from ghostrecon.service_apps.factory import build_app

playwright_sync_api = pytest.importorskip("playwright.sync_api")

NOW = "2026-07-07T00:00:00+00:00"


@pytest.fixture()
def page() -> Iterator[Any]:
    with playwright_sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except playwright_sync_api.Error as exc:
            pytest.skip(f"Playwright Chromium is not installed: {exc}")
        page = browser.new_page()
        try:
            yield page
        finally:
            browser.close()


@pytest.fixture()
def console_server() -> Iterator[dict[str, Any]]:
    mutations: list[dict[str, Any]] = []
    with _run_app(_gateway_app(mutations)) as gateway_url:
        settings = Settings(
            service_name="console-service",
            gateway_base_url=gateway_url,
            console_request_timeout_seconds=3,
        )
        with _run_app(build_app(settings)) as console_url:
            yield {"url": console_url, "mutations": mutations}


def test_sidebar_routes_change_url_content_and_active_state(page, console_server) -> None:
    base_url = console_server["url"]
    expected_routes = {
        "/": "Operator Overview",
        "/events": "Global Events",
        "/incidents": "Global Incidents",
        "/watchlists": "Watchlists",
        "/review": "Analyst Review",
        "/crm/exports": "CRM Targets and Export",
        "/sequences": "Sequence State",
        "/meetings": "Meeting Handoff",
        "/operations/sources": "Source Health",
    }

    page.goto(base_url)
    _heading(page, "Operator Overview").wait_for()
    _select_role(page, "analyst")

    for route, heading in expected_routes.items():
        label = "Overview" if route == "/" else _nav_label(heading)
        page.get_by_role("link", name=label).click()
        page.wait_for_url(f"**{route}")
        _heading(page, heading).wait_for()
        active = page.locator(".nav-link.active")
        assert active.count() == 1
        assert active.first.get_attribute("aria-current") == "page"
        assert console_server["mutations"] == []


def test_detail_links_refresh_filters_pagination_role_and_action(page, console_server) -> None:
    base_url = console_server["url"]

    page.goto(f"{base_url}/events?country=US")
    page.get_by_text("country: US").wait_for()
    page.get_by_role("link", name="Open").first.click()
    page.wait_for_url("**/events/event-1")
    _heading(page, "Event Detail").wait_for()
    assert page.locator(".nav-link.active").first.inner_text() == "Events"

    page.reload()
    _heading(page, "Event Detail").wait_for()

    page.goto(f"{base_url}/incidents")
    page.get_by_role("link", name="Next page").click()
    page.wait_for_url("**/incidents?cursor=incident-page-2*")
    page.get_by_text("cursor: incident-page-2").wait_for()

    page.goto(f"{base_url}/meetings")
    page.get_by_role("link", name="Open").first.click()
    page.wait_for_url("**/meetings/meeting-1")
    _heading(page, "Meeting Detail").wait_for()
    assert page.locator(".nav-link.active").first.inner_text() == "Meetings"

    page.goto(f"{base_url}/crm/exports/batch-1")
    _heading(page, "CRM Export Batch").wait_for()
    assert page.locator(".nav-link.active").first.inner_text() == "CRM Exports"

    page.goto(f"{base_url}/review")
    approve = page.locator('button[title="Approve"]').first
    assert approve.is_disabled()
    assert console_server["mutations"] == []
    _select_role(page, "analyst")
    approve = page.locator('button[title="Approve"]').first
    playwright_sync_api.expect(approve).to_be_enabled()
    assert console_server["mutations"] == []
    approve.click()
    page.get_by_text("Review candidate review-1 approved.").wait_for()
    assert any(
        mutation["path"] == "/v1/review/candidates/review-1/approve"
        for mutation in console_server["mutations"]
    )


def test_gateway_failure_renders_actionable_notice(page, console_server) -> None:
    page.goto(f"{console_server['url']}/events?source=fail")
    page.get_by_text("reporting unavailable").wait_for()
    page.get_by_text("Endpoint: /v1/reporting/events").wait_for()
    page.get_by_text("Status: 503").wait_for()


def _select_role(page, role: str) -> None:
    page.locator("#operator-role").click()
    page.get_by_text(role, exact=True).click()
    page.get_by_text(role, exact=True).wait_for()


def _heading(page, name: str):
    return page.get_by_role("heading", name=name, exact=True).first


def _nav_label(heading: str) -> str:
    return {
        "Global Events": "Events",
        "Global Incidents": "Incidents",
        "Analyst Review": "Review",
        "CRM Targets and Export": "CRM Exports",
        "Sequence State": "Sequences",
        "Meeting Handoff": "Meetings",
        "Source Health": "Sources",
    }.get(heading, heading)


@contextmanager
def _run_app(app: FastAPI) -> Iterator[str]:
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    _wait_for(url)
    try:
        yield url
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for(url: str) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{url}/healthz", timeout=0.5)
            if response.status_code < 500:
                return
        except httpx.HTTPError:
            time.sleep(0.1)
    raise RuntimeError(f"server did not start at {url}")


def _gateway_app(mutations: list[dict[str, Any]]) -> FastAPI:
    app = FastAPI()

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.api_route("/{path:path}", methods=["GET", "POST", "PATCH"])
    async def route(path: str, request: Request) -> dict[str, Any]:
        normalized = f"/{path}"
        if request.method in {"POST", "PATCH"}:
            body = await request.body()
            mutations.append(
                {
                    "method": request.method,
                    "path": normalized,
                    "payload": await request.json() if body else {},
                }
            )
            return {"id": "mutation-ok"}

        if normalized == "/v1/reporting/events" and request.query_params.get("source") == "fail":
            raise HTTPException(status_code=503, detail="reporting unavailable")
        return _payload_for(normalized)

    return app


def _payload_for(path: str) -> dict[str, Any]:
    metadata = {
        "generated_at": NOW,
        "watermarks": {"projection_generated_at": NOW},
        "projection_version": "reporting.v1.query",
        "stale": False,
        "degraded_dependencies": [],
    }
    payloads: dict[str, dict[str, Any]] = {
        "/v1/reporting/kpis/catalog": {"metadata": metadata, "kpis": {"demo": ["ready"]}},
        "/v1/reporting/source-health": {
            "metadata": metadata,
            "sources": [{"id": "source-1", "name": "Demo Source", "freshness_status": "fresh"}],
        },
        "/v1/reporting/events": {
            "metadata": metadata,
            "events": [
                {
                    "id": "event-1",
                    "name": "Demo Event",
                    "event_series_key": "demo",
                    "starts_at_utc": NOW,
                    "event_format": "hybrid",
                    "country": "US",
                    "confidence": "high",
                }
            ],
        },
        "/v1/reporting/events/event-1": {
            "metadata": metadata,
            "event": {"id": "event-1", "name": "Demo Event", "country": "US"},
        },
        "/v1/intelligence/events/event-1/participants": {
            "participants": [{"published_name": "Ada Analyst", "organization": "DemoSec"}],
        },
        "/v1/reporting/incidents": {
            "metadata": metadata,
            "next_cursor": "incident-page-2",
            "incidents": [
                {
                    "id": "incident-1",
                    "title": "Demo Incident",
                    "status": "candidate",
                    "version": 1,
                    "affected_companies": ["Acme"],
                }
            ],
        },
        "/v1/reporting/incidents/incident-1": {
            "metadata": metadata,
            "incident": {"id": "incident-1", "title": "Demo Incident", "version": 1},
        },
        "/v1/reporting/watch-targets": {
            "metadata": metadata,
            "watch_targets": [
                {
                    "id": "watch-1",
                    "display_name": "Acme",
                    "target_type": "company",
                    "enabled": True,
                    "version": 1,
                }
            ],
        },
        "/v1/reporting/review-queue": {
            "metadata": metadata,
            "candidates": [
                {
                    "id": "review-1",
                    "candidate_type": "account",
                    "target_type": "crm_export",
                    "reason_code": "demo",
                    "version": 1,
                    "policy_snapshot_hash": "hash",
                }
            ],
        },
        "/v1/reporting/crm-targets": {
            "metadata": metadata,
            "crm_targets": [
                {
                    "id": "crm-target-1",
                    "target_id": "account-1",
                    "target_type": "account",
                    "status": "approved",
                    "version": 1,
                }
            ],
        },
        "/v1/crm/exports/batch-1": {
            "id": "batch-1",
            "provider": "attio",
            "status": "partial_failure",
            "items": [{"crm_target_id": "crm-target-1", "status": "failed"}],
        },
        "/v1/sequences/enrollments": {
            "enrollments": [
                {"id": "enroll-1", "sequence_id": "seq-1", "status": "active"}
            ],
        },
        "/v1/reporting/meetings": {
            "metadata": metadata,
            "meetings": [
                {"id": "meeting-1", "subject": "Demo Meeting", "status": "scheduled"}
            ],
        },
        "/v1/reporting/meetings/meeting-1": {
            "metadata": metadata,
            "meeting": {"id": "meeting-1", "subject": "Demo Meeting", "status": "scheduled"},
        },
    }
    return payloads.get(path, {"metadata": metadata})
