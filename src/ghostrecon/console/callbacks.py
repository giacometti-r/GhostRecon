from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from dash import ALL, Input, Output, State, ctx, html, no_update

from ghostrecon.common.config import Settings
from ghostrecon.console.api import (
    ConsoleApiClient,
    ConsoleApiError,
    idempotency_key,
    normalize_role,
)
from ghostrecon.console.components import error_notice, icon
from ghostrecon.console.layouts import render_navigation, render_page
from ghostrecon.models.api import DashboardRole

ACTION_PATTERN = {
    "type": "dashboard-action",
    "kind": ALL,
    "action": ALL,
    "target_id": ALL,
    "version": ALL,
    "policy_hash": ALL,
    "enabled": ALL,
}

MUTATING_ROLES = {
    DashboardRole.ANALYST.value,
    DashboardRole.GOVERNANCE_REVIEWER.value,
    DashboardRole.ADMINISTRATOR.value,
}


def register_callbacks(dash_app: Any, settings: Settings) -> None:
    @dash_app.callback(
        Output("page-content", "children"),
        Input("console-url", "pathname"),
        Input("console-url", "search"),
        Input("operator-actor", "value"),
        Input("operator-role", "value"),
        Input("refresh-page", "n_clicks"),
        Input("mutation-refresh-token", "data"),
        Input("dismissed-incident-ids", "data"),
    )
    def route_page(
        pathname: str | None,
        search: str | None,
        actor: str | None,
        role: str | None,
        _refresh_clicks: int | None,
        _mutation_refresh: int | None,
        dismissed_incident_ids: list[str] | None,
    ) -> html.Div:
        return render_page(
            pathname,
            search,
            actor,
            role,
            settings,
            dismissed_incident_ids=dismissed_incident_ids,
        )

    @dash_app.callback(
        Output("sidebar-nav", "children"),
        Input("console-url", "pathname"),
    )
    def route_navigation(pathname: str | None) -> list[Any]:
        return render_navigation(pathname)

    @dash_app.callback(
        Output("mutation-status", "children"),
        Output("mutation-refresh-token", "data"),
        Output("mutation-status-clear", "disabled"),
        Output("dismissed-incident-ids", "data"),
        Input(ACTION_PATTERN, "n_clicks"),
        Input("mutation-status-clear", "n_intervals"),
        State({"type": "event-enrich-domain", "event_id": ALL}, "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        State("dismissed-incident-ids", "data"),
        prevent_initial_call=True,
    )
    def run_action(
        _clicks: list[int] | None,
        _clear_ticks: int | None,
        event_domains: list[str] | None,
        actor: str | None,
        role: str | None,
        token: int | None,
        dismissed_incident_ids: list[str] | None,
    ) -> tuple[Any, Any, Any, Any]:
        if ctx.triggered_id == "mutation-status-clear":
            return "", no_update, True, no_update
        action_id = ctx.triggered_id
        if not isinstance(action_id, dict):
            return no_update, no_update, no_update, no_update
        if _triggered_click_count() < 1:
            return no_update, no_update, no_update, no_update
        if action_id.get("kind") == "sequence" and action_id.get("action") == "pause":
            return no_update, no_update, no_update, no_update
        try:
            message = perform_dashboard_action(
                action_id,
                actor=actor or "dashboard",
                role=role,
                settings=settings,
                extra_payload={"domain": _first_value(event_domains)},
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False, no_update
        return (
            _success_notice(message),
            (token or 0) + 1,
            False,
            _dismissed_incidents(action_id, dismissed_incident_ids),
        )

    @dash_app.callback(
        Output("sequence-pause-target", "data"),
        Output("sequence-pause-modal", "className"),
        Output("sequence-pause-reason", "value"),
        Input(ACTION_PATTERN, "n_clicks"),
        prevent_initial_call=True,
    )
    def open_sequence_pause_modal(_clicks: list[int] | None) -> tuple[Any, str, str]:
        action_id = ctx.triggered_id
        if not isinstance(action_id, dict):
            return no_update, no_update, no_update
        if _triggered_click_count() < 1:
            return no_update, no_update, no_update
        if action_id.get("kind") != "sequence" or action_id.get("action") != "pause":
            return no_update, no_update, no_update
        return action_id, "modal-backdrop", ""

    @dash_app.callback(
        Output("sequence-pause-modal", "className", allow_duplicate=True),
        Output("sequence-pause-target", "data", allow_duplicate=True),
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input("sequence-pause-confirm", "n_clicks"),
        Input("sequence-pause-cancel", "n_clicks"),
        State("sequence-pause-target", "data"),
        State("sequence-pause-reason", "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def confirm_sequence_pause(
        confirm_clicks: int | None,
        cancel_clicks: int | None,
        action_id: dict[str, Any] | None,
        reason: str | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any, Any, Any]:
        triggered = ctx.triggered_id
        if triggered == "sequence-pause-cancel" and (cancel_clicks or 0) > 0:
            return "modal-backdrop hidden", {}, no_update, no_update, no_update
        if triggered != "sequence-pause-confirm" or (confirm_clicks or 0) < 1:
            return no_update, no_update, no_update, no_update, no_update
        if not action_id:
            return (
                "modal-backdrop hidden",
                {},
                error_notice("Action failed", "Missing sequence."),
                no_update,
                False,
            )
        if not (reason or "").strip():
            return (
                no_update,
                no_update,
                error_notice("Pause reason required", "Type a reason before confirming."),
                no_update,
                False,
            )
        try:
            message = perform_dashboard_action(
                action_id,
                actor=actor or "dashboard",
                role=role,
                settings=settings,
                extra_payload={"reason": reason.strip()},
            )
        except ConsoleApiError as exc:
            return no_update, no_update, error_notice("Action failed", str(exc)), no_update, False
        return "modal-backdrop hidden", {}, _success_notice(message), (token or 0) + 1, False

    @dash_app.callback(
        Output("manual-event-modal", "className"),
        Input("manual-event-open", "n_clicks"),
        Input("manual-event-cancel", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_manual_event_modal(open_clicks: int | None, cancel_clicks: int | None) -> str:
        triggered = ctx.triggered_id
        if triggered == "manual-event-open" and (open_clicks or 0) > 0:
            return "modal-backdrop"
        if triggered == "manual-event-cancel" and (cancel_clicks or 0) > 0:
            return "modal-backdrop hidden"
        return no_update

    @dash_app.callback(
        Output("manual-incident-modal", "className"),
        Input("manual-incident-open", "n_clicks"),
        Input("manual-incident-cancel", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_manual_incident_modal(open_clicks: int | None, cancel_clicks: int | None) -> str:
        triggered = ctx.triggered_id
        if triggered == "manual-incident-open" and (open_clicks or 0) > 0:
            return "modal-backdrop"
        if triggered == "manual-incident-cancel" and (cancel_clicks or 0) > 0:
            return "modal-backdrop hidden"
        return no_update

    @dash_app.callback(
        Output("event-edit-modal", "className"),
        Input("event-edit-open", "n_clicks"),
        Input("event-edit-cancel", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_event_edit_modal(open_clicks: int | None, cancel_clicks: int | None) -> str:
        triggered = ctx.triggered_id
        if triggered == "event-edit-open" and (open_clicks or 0) > 0:
            return "modal-backdrop"
        if triggered == "event-edit-cancel" and (cancel_clicks or 0) > 0:
            return "modal-backdrop hidden"
        return no_update

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Output("manual-event-modal", "className", allow_duplicate=True),
        Input("manual-event-submit", "n_clicks"),
        State("manual-event-name", "value"),
        State("manual-event-url", "value"),
        State("manual-event-start", "value"),
        State("manual-event-format", "value"),
        State("manual-event-venue", "value"),
        State("manual-event-street", "value"),
        State("manual-event-city", "value"),
        State("manual-event-region", "value"),
        State("manual-event-postcode", "value"),
        State("manual-event-country", "value"),
        State("manual-event-virtual-url", "value"),
        State("manual-event-topics", "value"),
        State("manual-event-source-items", "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def create_manual_event(
        clicks: int | None,
        name: str | None,
        canonical_url: str | None,
        starts_at: str | None,
        event_format: str | None,
        venue: str | None,
        street: str | None,
        city: str | None,
        region: str | None,
        postcode: str | None,
        country: str | None,
        virtual_url: str | None,
        topics: str | None,
        source_items: str | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any, Any]:
        if (clicks or 0) < 1:
            return no_update, no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot create events"),
                no_update,
                False,
                no_update,
            )
        if not (name or "").strip():
            return error_notice("Event name required"), no_update, False, no_update
        if not (canonical_url or "").strip() or not (starts_at or "").strip():
            return error_notice("Event URL and UTC start are required"), no_update, False, no_update
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        payload = {
            "name": name.strip(),
            "canonical_url": canonical_url.strip(),
            "starts_at_utc": _datetime_value(starts_at),
            "event_format": event_format or "unknown",
            "venue_name": _clean(venue),
            "street_address": _clean(street),
            "city": _clean(city),
            "region": _clean(region),
            "postcode": _clean(postcode),
            "country": _clean(country),
            "virtual_url": _clean(virtual_url),
            "topics": _csv(topics),
            "source_item_ids": _csv(source_items),
        }
        try:
            api.post(
                "/v1/intelligence/events/manual",
                payload=payload,
                idempotency_key=idempotency_key(
                    "manual-event", name.strip(), canonical_url.strip()
                ),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False, no_update
        return (
            _success_notice(f"Manual event {name.strip()} created."),
            (token or 0) + 1,
            False,
            "modal-backdrop hidden",
        )

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Output("event-edit-modal", "className", allow_duplicate=True),
        Input({"type": "event-edit-submit", "event_id": ALL, "version": ALL}, "n_clicks"),
        State("event-edit-name", "value"),
        State("event-edit-url", "value"),
        State("event-edit-start", "value"),
        State("event-edit-format", "value"),
        State("event-edit-venue", "value"),
        State("event-edit-street", "value"),
        State("event-edit-city", "value"),
        State("event-edit-region", "value"),
        State("event-edit-postcode", "value"),
        State("event-edit-country", "value"),
        State("event-edit-virtual-url", "value"),
        State("event-edit-topics", "value"),
        State("event-edit-source-items", "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def save_event_edit(
        clicks: list[int] | None,
        name: str | None,
        canonical_url: str | None,
        starts_at: str | None,
        event_format: str | None,
        venue: str | None,
        street: str | None,
        city: str | None,
        region: str | None,
        postcode: str | None,
        country: str | None,
        virtual_url: str | None,
        topics: str | None,
        source_items: str | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any, Any]:
        action_id = ctx.triggered_id
        if not isinstance(action_id, dict) or not any(clicks or []):
            return no_update, no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot edit events"),
                no_update,
                False,
                no_update,
            )
        event_id = str(action_id.get("event_id") or "")
        if not event_id:
            return error_notice("Action failed", "missing event id"), no_update, False, no_update
        payload = {
            "version": _int(action_id.get("version")),
            "name": _clean(name),
            "canonical_url": _clean(canonical_url),
            "starts_at_utc": _datetime_value(starts_at),
            "event_format": event_format or "unknown",
            "venue_name": _clean(venue),
            "street_address": _clean(street),
            "city": _clean(city),
            "region": _clean(region),
            "postcode": _clean(postcode),
            "country": _clean(country),
            "virtual_url": _clean(virtual_url),
            "topics": _csv(topics),
            "source_item_ids": _csv(source_items),
        }
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        try:
            api.patch(
                f"/v1/intelligence/events/{event_id}",
                payload=payload,
                idempotency_key=idempotency_key("event-edit", event_id, payload["version"]),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False, no_update
        return _success_notice("Event updated."), (token or 0) + 1, False, "modal-backdrop hidden"

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Output("manual-incident-modal", "className", allow_duplicate=True),
        Input("manual-incident-submit", "n_clicks"),
        State("manual-incident-title", "value"),
        State("manual-incident-company", "value"),
        State("manual-incident-type", "value"),
        State("manual-incident-first-observed", "value"),
        State("manual-incident-source-items", "value"),
        State("manual-incident-domains", "value"),
        State("manual-incident-vector", "value"),
        State("manual-incident-evidence-urls", "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def create_manual_incident(
        clicks: int | None,
        title: str | None,
        companies: str | None,
        incident_type: str | None,
        first_observed: str | None,
        source_items: str | None,
        domains: str | None,
        vector: str | None,
        evidence_urls: str | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any, Any]:
        if (clicks or 0) < 1:
            return no_update, no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot create incidents"),
                no_update,
                False,
                no_update,
            )
        if not (title or "").strip():
            return error_notice("Incident title required"), no_update, False, no_update
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        payload = {
            "title": title.strip(),
            "affected_companies": _csv(companies),
            "affected_domains": _csv(domains),
            "incident_type": _clean(incident_type),
            "attack_vector": _clean(vector),
            "first_observed_at": _datetime_value(first_observed),
            "source_item_ids": _csv(source_items),
            "evidence_urls": _csv(evidence_urls),
        }
        try:
            result = api.post(
                "/v1/intelligence/incidents/manual",
                payload=payload,
                idempotency_key=idempotency_key("manual-incident", title.strip()),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False, no_update
        count = len(result.get("incidents") or [])
        return (
            _success_notice(f"Manual incident {title.strip()} created ({count} row(s))."),
            (token or 0) + 1,
            False,
            "modal-backdrop hidden",
        )

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input({"type": "sequence-alert-submit", "enrollment_id": ALL}, "n_clicks"),
        State({"type": "sequence-alert-recipient", "enrollment_id": ALL}, "value"),
        State({"type": "sequence-alert-subject", "enrollment_id": ALL}, "value"),
        State({"type": "sequence-alert-body", "enrollment_id": ALL}, "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def create_sequence_alert(
        clicks: list[int] | None,
        recipients: list[str] | None,
        subjects: list[str] | None,
        bodies: list[str] | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any]:
        action_id = ctx.triggered_id
        if not isinstance(action_id, dict) or not any(clicks or []):
            return no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot create alerts"),
                no_update,
                False,
            )
        recipient = _first_value(recipients)
        subject = _first_value(subjects)
        body = _first_value(bodies)
        if not recipient or not subject or not body:
            return error_notice("Alert fields required"), no_update, False
        enrollment_id = str(action_id.get("enrollment_id") or "")
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        try:
            api.post(
                f"/v1/sequences/enrollments/{enrollment_id}/alerts",
                payload={"recipient_email": recipient, "subject": subject, "body": body},
                idempotency_key=idempotency_key("sequence-alert", enrollment_id),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False
        return _success_notice("Reminder alert created."), (token or 0) + 1, False

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input("sequence-create-submit", "n_clicks"),
        State("sequence-create-name", "value"),
        State("sequence-create-owner", "value"),
        State("sequence-create-steps", "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def create_sequence_definition(
        clicks: int | None,
        name: str | None,
        owner: str | None,
        steps_json: str | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any]:
        if (clicks or 0) < 1:
            return no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot create sequences"),
                no_update,
                False,
            )
        try:
            parsed_steps = json.loads(steps_json or "[]")
        except json.JSONDecodeError as exc:
            return error_notice("Invalid steps JSON", str(exc)), no_update, False
        steps = [_sequence_step_payload(step) for step in parsed_steps if isinstance(step, dict)]
        if not name or not steps:
            return error_notice("Sequence name and steps are required"), no_update, False
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        try:
            api.post(
                "/v1/sequences",
                payload={
                    "name": name.strip(),
                    "owner_id": (owner or "").strip() or None,
                    "steps": steps,
                },
                idempotency_key=idempotency_key("sequence-create", name.strip()),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False
        return _success_notice("Sequence definition created."), (token or 0) + 1, False

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input({"type": "crm-prospect-import", "provider_record_id": ALL}, "n_clicks"),
        State("crm-prospect-sequence", "value"),
        State("crm-prospect-approval-reason", "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def import_crm_prospect(
        clicks: list[int] | None,
        sequence_id: str | None,
        approval_reason: str | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any]:
        action_id = ctx.triggered_id
        if not isinstance(action_id, dict) or not any(clicks or []):
            return no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot import prospects"),
                no_update,
                False,
            )
        provider_record_id = str(action_id.get("provider_record_id") or "")
        if not provider_record_id or not sequence_id:
            return error_notice("Prospect and sequence are required"), no_update, False
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        try:
            api.post(
                "/v1/sequences/enrollments/import-crm-prospect",
                payload={
                    "provider_record_id": provider_record_id,
                    "sequence_id": sequence_id,
                    "outreach_approved": True,
                    "approval_reason": approval_reason or "Approved from dashboard CRM import.",
                },
                idempotency_key=idempotency_key("crm-prospect-import", provider_record_id),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False
        return _success_notice("CRM prospect imported and assigned."), (token or 0) + 1, False

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input({"type": "sequence-edit-submit", "sequence_id": ALL}, "n_clicks"),
        State("sequence-edit-name", "value"),
        State("sequence-edit-owner", "value"),
        State("sequence-edit-status", "value"),
        State("sequence-edit-steps", "value"),
        State("sequence-edit-version", "data"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def save_sequence_definition(
        clicks: list[int] | None,
        name: str | None,
        owner: str | None,
        status: str | None,
        steps_json: str | None,
        version: int | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any]:
        action_id = ctx.triggered_id
        if not isinstance(action_id, dict) or not any(clicks or []):
            return no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot edit sequences"),
                no_update,
                False,
            )
        try:
            parsed_steps = json.loads(steps_json or "[]")
        except json.JSONDecodeError as exc:
            return error_notice("Invalid steps JSON", str(exc)), no_update, False
        steps = [_sequence_step_payload(step) for step in parsed_steps if isinstance(step, dict)]
        sequence_id = str(action_id.get("sequence_id") or "")
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        try:
            api.patch(
                f"/v1/sequences/{sequence_id}",
                payload={
                    "name": (name or "").strip() or None,
                    "owner_id": (owner or "").strip() or None,
                    "status": status,
                    "steps": steps,
                    "expected_version": version,
                },
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False
        return _success_notice("Sequence definition updated."), (token or 0) + 1, False


def perform_dashboard_action(
    action_id: dict[str, Any],
    *,
    actor: str,
    role: str | None,
    settings: Settings,
    client: ConsoleApiClient | None = None,
    client_factory: type[httpx.Client] = httpx.Client,
    extra_payload: dict[str, Any] | None = None,
) -> str:
    normalized_role = normalize_role(role)
    if normalized_role not in MUTATING_ROLES:
        raise ConsoleApiError("viewer role cannot perform dashboard mutations", status_code=403)

    api = client or ConsoleApiClient.from_settings(
        settings,
        actor=actor,
        role=normalized_role,
        client_factory=client_factory,
    )
    kind = str(action_id.get("kind") or "")
    action = str(action_id.get("action") or "")
    target_id = str(action_id.get("target_id") or "")
    if not kind or not action or not target_id:
        raise ConsoleApiError("dashboard action is missing a target", status_code=400)

    if kind == "review":
        payload = {
            "version": _int(action_id.get("version")),
            "reason_code": f"dashboard_{action}",
            "reason": "Sprint 12 dashboard review action.",
            "policy_snapshot_hash": action_id.get("policy_hash"),
            "evidence_snapshot": {},
            "target_scope": "crm_export",
        }
        api.post(
            f"/v1/review/candidates/{target_id}/{action}",
            payload=payload,
            idempotency_key=idempotency_key(f"review-{action}", target_id),
        )
        return f"Review candidate {target_id} {action}d."

    if kind == "bulk-review":
        candidate_ids = [candidate_id for candidate_id in target_id.split(",") if candidate_id]
        if not candidate_ids:
            raise ConsoleApiError("bulk review requires at least one candidate", status_code=400)
        decision = "approved" if action == "approve" else "rejected"
        payload = {
            "candidate_ids": candidate_ids,
            "decision": decision,
            "candidate_versions": _version_map(action_id.get("version")),
            "reason_code": f"dashboard_bulk_{action}",
            "reason": "Sprint 12 dashboard bulk review action.",
            "policy_snapshot_hash": action_id.get("policy_hash"),
            "evidence_snapshot": {},
        }
        api.post(
            "/v1/review/candidates/bulk-decision",
            payload=payload,
            idempotency_key=idempotency_key(f"bulk-review-{action}"),
        )
        return f"Bulk review {action} submitted for {len(candidate_ids)} candidate(s)."

    if kind == "crm-export":
        api.post(
            "/v1/crm/exports",
            payload={
                "crm_target_ids": [target_id],
                "provider": "attio",
                "reason": "Sprint 12 dashboard export action.",
            },
            idempotency_key=idempotency_key("crm-export", target_id),
        )
        return f"CRM export started for target {target_id}."

    if kind == "crm-retry":
        api.post(
            f"/v1/crm/exports/{target_id}/retry-failed",
            payload={"item_ids": []},
            idempotency_key=idempotency_key("crm-retry", target_id),
        )
        return f"Retry requested for CRM export batch {target_id}."

    if kind == "incident":
        return _perform_incident_action(api, action, target_id, action_id)

    if kind == "watch":
        if action == "find-contact":
            result = api.post(
                f"/v1/enrichment/watch-targets/{target_id}/find-contact",
                payload={},
                idempotency_key=idempotency_key("watch-find-contact", target_id),
            )
            count = len(result.get("contact_candidates") or [])
            return f"Watch target {target_id} contact discovery returned {count} candidate(s)."
        if action != "toggle":
            raise ConsoleApiError(f"unsupported watch action {action}", status_code=400)
        api.patch(
            f"/v1/intelligence/watch-targets/{target_id}",
            payload={
                "enabled": bool(action_id.get("enabled")),
                "version": _int(action_id.get("version")),
            },
            idempotency_key=idempotency_key("watch-toggle", target_id),
        )
        state = "enabled" if action_id.get("enabled") else "paused"
        return f"Watch target {target_id} {state}."

    if kind == "contact-candidate":
        if action != "discover-domain":
            raise ConsoleApiError(f"unsupported contact candidate action {action}", status_code=400)
        result = api.post(
            f"/v1/enrichment/contact-candidates/{target_id}/discover-domain",
            payload={},
            idempotency_key=idempotency_key("contact-domain", target_id),
        )
        domain = result.get("discovered_domain")
        return (
            f"Contact candidate {target_id} domain discovered: {domain}."
            if domain
            else f"Contact candidate {target_id} routed to review for domain discovery."
        )

    if kind == "sequence":
        if action not in {"pause", "resume", "cancel"}:
            raise ConsoleApiError(f"unsupported sequence action {action}", status_code=400)
        api.post(
            f"/v1/sequences/enrollments/{target_id}/{action}",
            payload={"reason": _action_reason(action, extra_payload)},
        )
        return f"Sequence enrollment {target_id} {action} requested."

    if kind == "sequence-activity":
        if action == "approve-email":
            api.post(
                f"/v1/sequences/activities/{target_id}/approve-email",
                payload={"reason": _action_reason(action, extra_payload)},
            )
            return f"Sequence email activity {target_id} approved."
        if action == "complete":
            api.post(
                f"/v1/sequences/activities/{target_id}/complete",
                payload={"reason": _action_reason(action, extra_payload)},
            )
            return f"Sequence call activity {target_id} completed."
        if action == "schedule-meeting":
            start = datetime.now(UTC) + timedelta(days=1)
            end = start + timedelta(minutes=30)
            api.post(
                f"/v1/sequences/activities/{target_id}/schedule-meeting",
                payload={
                    "subject": "Security discovery",
                    "location": "Google Meet",
                    "start_at": start.isoformat(),
                    "end_at": end.isoformat(),
                    "timezone": "UTC",
                    "attendees": [],
                },
                idempotency_key=idempotency_key("sequence-meeting", target_id),
            )
            return f"Sequence meeting activity {target_id} scheduled."
        raise ConsoleApiError(f"unsupported sequence activity action {action}", status_code=400)

    if kind == "event-participant":
        domain = str((extra_payload or {}).get("domain") or "").strip()
        if not domain:
            raise ConsoleApiError("domain is required to enrich a participant", status_code=400)
        result = api.post(
            f"/v1/enrichment/event-participants/{target_id}/enrich-target",
            payload={"domain": domain},
            idempotency_key=idempotency_key("participant-enrichment-queue", target_id),
        )
        verified = result.get("verified_email")
        return (
            f"Participant {target_id} queued with {verified}."
            if verified
            else f"Participant {target_id} added to enrichment queue."
        )

    if kind == "meeting":
        return _perform_meeting_action(api, action, target_id)

    raise ConsoleApiError(f"unsupported dashboard action {kind}", status_code=400)


def _perform_incident_action(
    api: ConsoleApiClient,
    action: str,
    target_id: str,
    action_id: dict[str, Any],
) -> str:
    if action == "promote":
        version = action_id.get("version")
        if version in (None, ""):
            raise ConsoleApiError("incident action requires an optimistic version", status_code=409)
        api.post(
            f"/v1/intelligence/incidents/{target_id}/promote-to-watchlist",
            payload={"version": _int(version)},
            idempotency_key=idempotency_key("incident-watch", target_id),
        )
        return f"Incident {target_id} added to watchlist."
    if action in {"corroborate", "reject", "revert"}:
        version = action_id.get("version")
        if version in (None, ""):
            raise ConsoleApiError("incident action requires an optimistic version", status_code=409)
        payload = {
            "version": _int(version),
            "reason_code": f"dashboard_incident_{action}",
            "reason": "Sprint 17/18 dashboard incident decision.",
            "evidence_snapshot": {},
            "policy_snapshot": {},
        }
        api.post(
            f"/v1/governance/incidents/{target_id}/{action}",
            payload=payload,
            idempotency_key=idempotency_key(f"incident-{action}", target_id),
        )
        return f"Incident {target_id} {action} action submitted."
    raise ConsoleApiError(f"unsupported incident action {action}", status_code=400)


def _perform_meeting_action(api: ConsoleApiClient, action: str, target_id: str) -> str:
    if action == "prep":
        api.post(
            f"/v1/meetings/{target_id}/prep-packet",
            payload={},
            idempotency_key=idempotency_key("meeting-prep", target_id),
        )
        return f"Prep packet requested for meeting {target_id}."
    if action == "outcome":
        api.post(
            f"/v1/meetings/{target_id}/outcome",
            payload={
                "outcome_status": "completed",
                "outcome_notes": "Recorded from Sprint 12 dashboard.",
                "next_steps": [],
                "follow_up_tasks": [],
            },
            idempotency_key=idempotency_key("meeting-outcome", target_id),
        )
        return f"Outcome recorded for meeting {target_id}."
    if action == "cancel":
        api.post(
            f"/v1/meetings/{target_id}/cancel",
            payload={"reason": "Sprint 12 dashboard cancellation."},
        )
        return f"Cancel requested for meeting {target_id}."
    if action == "retry-sync":
        api.post(f"/v1/meetings/{target_id}/retry-sync", payload={})
        return f"CRM sync retry requested for meeting {target_id}."
    raise ConsoleApiError(f"unsupported meeting action {action}", status_code=400)


def _success_notice(message: str) -> html.Div:
    return html.Div([icon("check-circle"), html.Span(message)], className="success-notice")


def _first_value(values: list[Any] | None) -> Any:
    for value in values or []:
        if value not in (None, ""):
            return value
    return None


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _csv(value: Any) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _datetime_value(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    if "T" in text and "+" not in text and not text.endswith("Z"):
        return f"{text}:00Z" if len(text) == 16 else f"{text}Z"
    return text


def _dismissed_incidents(
    action_id: dict[str, Any], dismissed_incident_ids: list[str] | None
) -> Any:
    if action_id.get("kind") != "incident" or action_id.get("action") not in {
        "promote",
        "reject",
    }:
        return no_update
    target_id = str(action_id.get("target_id") or "")
    if not target_id:
        return no_update
    dismissed = [str(item) for item in dismissed_incident_ids or []]
    if target_id not in dismissed:
        dismissed.append(target_id)
    return dismissed


def _action_reason(action: str, extra_payload: dict[str, Any] | None) -> str:
    reason = str((extra_payload or {}).get("reason") or "").strip()
    return reason or f"Sprint 12 dashboard {action} action."


def _sequence_step_payload(step: dict[str, Any]) -> dict[str, Any]:
    channel = step.get("channel") or "email"
    payload = {
        "step_order": step.get("step_order"),
        "delay_seconds": step.get("delay_seconds") or 0,
        "channel": channel,
        "requires_approval": step.get("requires_approval"),
        "step_metadata": step.get("step_metadata") or {},
    }
    if step.get("subject_template") is not None:
        payload["subject_template"] = step.get("subject_template")
    elif channel == "email":
        payload["subject_template"] = "Follow up"
    if step.get("body_template") is not None:
        payload["body_template"] = step.get("body_template")
    elif channel == "email":
        payload["body_template"] = "Checking in."
    return payload


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1


def _version_map(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _triggered_click_count() -> int:
    triggered = getattr(ctx, "triggered", None) or []
    if not triggered:
        return 0
    value = triggered[0].get("value")
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
