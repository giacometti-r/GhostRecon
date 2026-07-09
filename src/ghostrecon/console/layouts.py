from __future__ import annotations

import json
from collections import Counter
from typing import Any
from urllib.parse import parse_qs

from dash import dcc, html
from plotly import graph_objects as go

from ghostrecon.common.config import Settings
from ghostrecon.console.api import (
    ConsoleApiClient,
    ConsoleApiError,
    dashboard_context_from_headers,
)
from ghostrecon.console.components import (
    action_button,
    detail_panel,
    empty_state,
    error_notice,
    format_duration,
    human_label,
    icon,
    metadata_banner,
    metadata_details,
    nav_link,
    page_header,
    query_badges,
    records_table,
    summary_tile,
)
from ghostrecon.models.api import DashboardRole

NAV_ITEMS = [
    ("Overview", "/", "layout-dashboard"),
    ("Events", "/events", "calendar-days"),
    ("Incidents", "/incidents", "shield-alert"),
    ("Watchlists", "/watchlists", "radar"),
    ("Review", "/review", "clipboard-check"),
    ("CRM Exports", "/crm/exports", "upload-cloud"),
    ("Sequences", "/sequences", "send"),
    ("Meetings", "/meetings", "calendar-check"),
    ("Sources", "/operations/sources", "activity"),
]

REPORTING_LIMIT = 50


def build_shell(settings: Settings) -> html.Div:
    context = dashboard_context_from_headers()
    role_options = [
        {"label": role.value.replace("_", " "), "value": role.value} for role in DashboardRole
    ]
    return html.Div(
        [
            dcc.Location(id="console-url", refresh=False),
            dcc.Store(id="mutation-refresh-token", data=0),
            dcc.Store(id="sequence-pause-target", data={}),
            dcc.Store(id="dismissed-incident-ids", data=[]),
            dcc.Interval(
                id="mutation-status-clear",
                interval=4000,
                n_intervals=0,
                disabled=True,
            ),
            html.Header(
                [
                    html.Div(
                        [html.Div("GhostRecon", className="brand"), html.Div("Console")],
                        className="brand-block",
                    ),
                    html.Div(
                        [
                            html.Label("Actor", htmlFor="operator-actor"),
                            dcc.Input(
                                id="operator-actor",
                                value=context.actor,
                                type="text",
                                debounce=True,
                            ),
                            html.Label("Role", htmlFor="operator-role"),
                            dcc.Dropdown(
                                id="operator-role",
                                value=context.role,
                                options=role_options,
                                clearable=False,
                                searchable=False,
                            ),
                            html.Button(
                                [icon("refresh-cw"), html.Span("Refresh")],
                                id="refresh-page",
                                n_clicks=0,
                                className="icon-button",
                            ),
                        ],
                        className="operator-context",
                    ),
                ],
                className="console-header",
            ),
            html.Div(
                [
                    html.Nav(
                        render_navigation("/"),
                        id="sidebar-nav",
                        className="sidebar-nav",
                        **{"aria-label": "Dashboard navigation"},
                    ),
                    html.Main(
                        [
                            html.Div(id="mutation-status"),
                            html.Div(id="page-content"),
                        ],
                        className="console-main",
                    ),
                ],
                className="console-body",
            ),
            html.Footer(
                f"Gateway: {settings.gateway_base_url}",
                className="console-footer",
            ),
            _sequence_pause_modal(),
        ],
        className="console-app",
    )


def render_page(
    pathname: str | None,
    search: str | None,
    actor: str | None,
    role: str | None,
    settings: Settings,
    *,
    client: ConsoleApiClient | None = None,
    dismissed_incident_ids: list[str] | None = None,
) -> html.Div:
    context_role = _normalize_role(role)
    api = client or ConsoleApiClient.from_settings(
        settings,
        actor=actor or "dashboard",
        role=context_role,
    )
    params = _params(search)
    path = (pathname or "/").rstrip("/") or "/"
    try:
        if path == "/":
            return overview_page(api, params)
        if path == "/events":
            return events_page(api, params, role=context_role)
        if path.startswith("/events/"):
            return event_detail_page(api, path.rsplit("/", 1)[-1], role=context_role)
        if path == "/incidents":
            return incidents_page(
                api,
                params,
                role=context_role,
                dismissed_incident_ids=dismissed_incident_ids,
            )
        if path.startswith("/incidents/"):
            return incident_detail_page(api, path.rsplit("/", 1)[-1], role=context_role)
        if path == "/watchlists":
            return watchlists_page(api, params, role=context_role)
        if path == "/review/enrichment":
            return enrichment_review_page(api, params)
        if path == "/review":
            return review_page(api, params, role=context_role)
        if path == "/crm/exports":
            return crm_exports_page(api, params, role=context_role)
        if path.startswith("/crm/exports/"):
            return crm_export_detail_page(api, path.rsplit("/", 1)[-1], role=context_role)
        if path == "/sequences":
            return sequences_page(api, params, role=context_role)
        if path.startswith("/sequences/enrollments/"):
            return sequence_enrollment_detail_page(api, path.rsplit("/", 1)[-1], role=context_role)
        if path.startswith("/sequences/definitions/"):
            return sequence_definition_detail_page(api, path.rsplit("/", 1)[-1], role=context_role)
        if path == "/meetings":
            return meetings_page(api, params, role=context_role)
        if path.startswith("/meetings/"):
            return meeting_detail_page(api, path.rsplit("/", 1)[-1], role=context_role)
        if path == "/operations/sources":
            return source_health_page(api, params)
    except ConsoleApiError as exc:
        return _page("Gateway error", [], [error_notice(str(exc), detail=exc.path)])
    return _page("Not found", [], [empty_state(f"No dashboard route exists for {path}.")])


def render_navigation(pathname: str | None) -> list[Any]:
    active_href = _active_nav_href(pathname)
    return [
        nav_link(label, href, icon_name, active=href == active_href)
        for label, href, icon_name in NAV_ITEMS
    ]


def _active_nav_href(pathname: str | None) -> str:
    path = (pathname or "/").rstrip("/") or "/"
    if path == "/":
        return "/"
    matches = [
        href
        for _, href, _ in NAV_ITEMS
        if href != "/" and (path == href or path.startswith(f"{href}/"))
    ]
    if not matches:
        return ""
    return max(matches, key=len)


def overview_page(client: ConsoleApiClient, params: dict[str, Any]) -> html.Div:
    payloads = {
        "kpis": _safe_get(client, "/v1/reporting/kpis/catalog"),
        "sources": _safe_get(client, "/v1/reporting/source-health", {"limit": 25}),
        "review": _safe_get(client, "/v1/reporting/review-queue", {"limit": 25}),
        "crm": _safe_get(client, "/v1/reporting/crm-targets", {"limit": 25}),
        "meetings": _safe_get(client, "/v1/reporting/meetings", {"limit": 25}),
    }
    tiles = [
        summary_tile("Open review", _count(payloads["review"], "candidates")),
        summary_tile("CRM targets", _count(payloads["crm"], "crm_targets")),
        summary_tile("Meetings", _count(payloads["meetings"], "meetings")),
        summary_tile("Sources", _count(payloads["sources"], "sources")),
    ]
    kpis = payloads["kpis"].get("kpis", {}) if isinstance(payloads["kpis"], dict) else {}
    children = [
        html.Div(tiles, className="summary-grid"),
        detail_panel(
            "KPI catalog",
            [
                (human_label(family), ", ".join(human_label(value) for value in values))
                for family, values in kpis.items()
            ],
        ),
        records_table(
            payloads["sources"].get("sources", []),
            [
                ("Source", "name"),
                ("Kind", "source_kind"),
                ("Freshness", "freshness_status"),
                ("Lag seconds", "freshness_lag_seconds"),
            ],
        ),
    ]
    return _page("Operator Overview", list(payloads.values()), children, query_params=params)


def events_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div:
    payload = _safe_get(
        client,
        "/v1/reporting/events",
        _filtered(params, "series", "source", "country", "event_format", "topic", "cursor"),
    )
    events = payload.get("events", [])
    children = [
        query_badges(params),
        _event_map(events),
        _manual_event_form(role),
        records_table(
            events,
            [
                ("Name", "name"),
                ("Series", "event_series_key"),
                ("Starts", "starts_at_utc"),
                ("Format", "event_format"),
                ("Country", "country"),
            ],
            actions=lambda record: [
                dcc.Link("Open", href=f"/events/{record.get('id')}", refresh=False)
            ],
        ),
        _pagination(payload, "/events", params),
    ]
    return _page("Global Events", [payload], children)


def event_detail_page(client: ConsoleApiClient, event_id: str, *, role: str) -> html.Div:
    payload = _safe_get(client, f"/v1/reporting/events/{event_id}")
    participants = _safe_get(client, f"/v1/intelligence/events/{event_id}/participants")
    queued = _safe_get(
        client,
        "/v1/enrichment/contact-candidates",
        {"origin_type": "event_participant", "limit": 500},
    )
    event = payload.get("event", {})
    participant_rows = _participant_rows(
        participants.get("participants", []),
        queued.get("candidates", []),
    )
    children = [
        _event_edit_modal(event, role),
        detail_panel(
            "Event detail",
            [
                ("Name", event.get("name")),
                ("Series", event.get("event_series_key")),
                ("Original time", event.get("original_start")),
                ("UTC time", event.get("starts_at_utc")),
                ("Timezone", event.get("iana_timezone") or event.get("source_timezone")),
                ("Venue", event.get("venue_name")),
                ("Location", _location(event)),
                ("Address", _address(event)),
                ("Canonical URL", event.get("canonical_url")),
                ("Topics", _inline_list(event.get("topics"))),
                ("Source items", _inline_list(event.get("source_item_ids"))),
            ],
        ),
        records_table(
            participant_rows,
            [
                ("Name", "published_name"),
                ("Organization", "organization"),
                ("Role", "published_role"),
                ("Reuse", "reuse_state"),
                ("Contact allowed", "contact_extraction_allowed"),
                ("CRM export allowed", "crm_export_allowed"),
            ],
            actions=lambda record: _participant_actions(record, role),
        ),
        _participant_enrich_form(event_id, role),
        metadata_details(payload)
        if role == DashboardRole.GOVERNANCE_REVIEWER.value
        else html.Div(),
    ]
    return _page("Event Detail", [payload], children)


def incidents_page(
    client: ConsoleApiClient,
    params: dict[str, Any],
    *,
    role: str,
    dismissed_incident_ids: list[str] | None = None,
) -> html.Div:
    payload = _safe_get(
        client,
        "/v1/reporting/incidents",
        _filtered(
            params,
            "status",
            "source",
            "company",
            "attack_vector",
            "incident_type",
            "cursor",
        ),
    )
    dismissed = {str(item) for item in dismissed_incident_ids or []}
    incidents = [
        incident
        for incident in payload.get("incidents", [])
        if str(incident.get("id")) not in dismissed
    ]
    incident_rows = [_incident_table_row(incident) for incident in incidents]
    children = [
        query_badges(params),
        _manual_incident_form(role),
        records_table(
            incident_rows,
            [
                ("Title", "title"),
                ("Status", "status"),
                ("Companies", "company_display"),
                ("Attack", "attack_vector"),
                ("Evidence", "evidence_display"),
            ],
            actions=lambda record: _incident_actions(record, role),
        ),
        _pagination(payload, "/incidents", params),
    ]
    return _page("Global Incidents", [payload], children)


def incident_detail_page(client: ConsoleApiClient, incident_id: str, *, role: str) -> html.Div:
    payload = _safe_get(client, f"/v1/reporting/incidents/{incident_id}")
    incident = payload.get("incident", {})
    children = [
        detail_panel(
            "Incident detail",
            [
                ("Title", incident.get("title")),
                ("Status", incident.get("status")),
                ("Affected companies", _inline_list(incident.get("affected_companies"))),
                ("Domains", _inline_list(incident.get("affected_domains"))),
                ("Type", incident.get("incident_type")),
                ("Attack vector", incident.get("attack_vector")),
                ("First observed", incident.get("first_observed_at")),
                ("Last observed", incident.get("last_observed_at")),
                ("Evidence families", _inline_list(incident.get("evidence_families"))),
                ("Evidence URLs", _inline_list(incident.get("evidence_urls"))),
                ("Source items", _inline_list(incident.get("source_item_ids"))),
            ],
        ),
        html.Div(_incident_actions(incident, role, include_open=False), className="detail-actions"),
        metadata_details(payload)
        if role == DashboardRole.GOVERNANCE_REVIEWER.value
        else html.Div(),
    ]
    return _page("Incident Detail", [payload], children)


def watchlists_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div:
    payload = _safe_get(
        client,
        "/v1/reporting/watch-targets",
        _filtered(params, "target_type", "enabled", "owner", "cursor"),
    )
    children = [
        query_badges(params),
        records_table(
            payload.get("watch_targets", []),
            [
                ("Name", "display_name"),
                ("Type", "target_type"),
                ("Key", "canonical_target_key"),
                ("Owner", "owner"),
                ("Enabled", "enabled"),
                ("Origin incident", "origin_incident_id"),
            ],
            actions=lambda record: _watch_actions(record, role),
        ),
        _pagination(payload, "/watchlists", params),
    ]
    return _page("Watchlists", [payload], children)


def review_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div:
    payload = _safe_get(
        client,
        "/v1/reporting/review-queue",
        _filtered(params, "status", "candidate_type", "target_type", "cursor"),
    )
    children = [
        query_badges(params),
        dcc.Link(
            "Open enrichment queue",
            href="/review/enrichment",
            refresh=False,
            className="text-link",
        ),
        html.Div(
            _bulk_review_actions(payload.get("candidates", []), role),
            className="bulk-actions",
        ),
        records_table(
            payload.get("candidates", []),
            [
                ("Candidate", "candidate_type"),
                ("Target", "target_type"),
                ("Reason", "reason_code"),
                ("SLA", "sla_due_at"),
                ("Version", "version"),
            ],
            actions=lambda record: _review_actions(record, role),
        ),
        _pagination(payload, "/review", params),
    ]
    return _page("Analyst Review", [payload], children)


def enrichment_review_page(client: ConsoleApiClient, params: dict[str, Any]) -> html.Div:
    contacts = _safe_get(client, "/v1/enrichment/contact-candidates", _filtered(params, "status"))
    cases = _safe_get(client, "/v1/enrichment/entity-resolutions", _filtered(params, "status"))
    contact_rows = [_contact_queue_row(candidate) for candidate in contacts.get("candidates", [])]
    children = [
        records_table(
            contact_rows,
            [
                ("Name", "published_name"),
                ("Organization", "organization"),
                ("Role", "role_scope"),
                ("Domain", "domain"),
                ("Status", "status"),
                ("Reuse", "reuse_state"),
                ("Provenance", "provenance"),
                ("Verified email", "verified_email"),
                ("Reason", "eligibility_reason"),
            ],
        ),
        records_table(
            cases.get("cases", []),
            [
                ("Input", "input_name"),
                ("Domain", "input_domain"),
                ("Resolved", "resolved_name"),
                ("Status", "status"),
                ("Confidence", "confidence"),
            ],
        ),
    ]
    return _page("Contact Enrichment Queue", [], children, query_params=params)


def crm_exports_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div:
    payload = _safe_get(
        client,
        "/v1/reporting/crm-targets",
        _filtered(params, "status", "target_type", "export_status", "cursor"),
    )
    children = [
        query_badges(params),
        records_table(
            payload.get("crm_targets", []),
            [
                ("Target type", "target_type"),
                ("Target ID", "target_id"),
                ("Status", "status"),
                ("Export", "export_status"),
                ("Version", "version"),
            ],
            actions=lambda record: _crm_target_actions(record, role),
        ),
        _pagination(payload, "/crm/exports", params),
    ]
    return _page("CRM Targets and Export", [payload], children)


def crm_export_detail_page(client: ConsoleApiClient, batch_id: str, *, role: str) -> html.Div:
    batch = _safe_get(client, f"/v1/crm/exports/{batch_id}")
    children = [
        detail_panel(
            "Batch detail",
            [
                ("Batch", batch.get("id")),
                ("Provider", batch.get("provider")),
                ("Requested by", batch.get("requested_by")),
                ("Status", batch.get("status")),
                ("Selection hash", batch.get("selection_hash")),
                ("Counts", batch.get("counts")),
                ("Reconciliation", batch.get("reconciliation_summary")),
            ],
        ),
        html.Div(_crm_batch_actions(batch, role), className="detail-actions"),
        records_table(
            batch.get("items", []),
            [
                ("Target", "crm_target_id"),
                ("Operation", "operation"),
                ("Provider object", "provider_object"),
                ("Status", "status"),
                ("Attempts", "attempt_count"),
                ("Last error", "last_error"),
            ],
        ),
    ]
    return _page("CRM Export Batch", [], children)


def sequences_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div:
    payload = _safe_get(client, "/v1/sequences/enrollments", _filtered(params, "status"))
    sequences = _safe_get(client, "/v1/sequences", {"limit": REPORTING_LIMIT})
    children = [
        query_badges(params),
        html.Section(
            [
                html.H2("Sequence definitions"),
                records_table(
                    [_sequence_row(sequence) for sequence in sequences.get("sequences", [])],
                    [
                        ("Name", "name"),
                        ("Owner", "owner_id"),
                        ("Channel", "channel"),
                        ("Status", "status"),
                        ("Steps", "step_count"),
                    ],
                    actions=lambda record: [
                        dcc.Link(
                            "Open",
                            href=f"/sequences/definitions/{record.get('id')}",
                            refresh=False,
                        )
                    ],
                ),
            ],
            className="detail-panel",
        ),
        records_table(
            [_sequence_enrollment_row(enrollment) for enrollment in payload.get("enrollments", [])],
            [
                ("Prospect", "contact_name"),
                ("Company", "account_name"),
                ("Email", "contact_email"),
                ("Sequence", "sequence_name"),
                ("Status", "status"),
                ("Current step", "current_step_order"),
                ("Next step", "next_step_at"),
                ("Pause reason", "pause_reason"),
            ],
            actions=lambda record: _sequence_actions(record, role),
        ),
        html.Div(
            "The console exposes pause, resume, cancel, and unsubscribe controls; it never "
            "offers a send-now bypass.",
            className="operator-note",
        ),
    ]
    return _page("Sequence State", [], children)


def sequence_enrollment_detail_page(
    client: ConsoleApiClient, enrollment_id: str, *, role: str
) -> html.Div:
    enrollment = _safe_get(client, f"/v1/sequences/enrollments/{enrollment_id}")
    sequence_id = enrollment.get("sequence_id")
    sequence = (
        _safe_get(client, f"/v1/sequences/{sequence_id}")
        if sequence_id and "_error" not in enrollment
        else {}
    )
    children = [
        detail_panel(
            "Enrollment",
            [
                ("Prospect", enrollment.get("contact_name")),
                ("Email", enrollment.get("contact_email")),
                ("Company", enrollment.get("account_name") or enrollment.get("account_domain")),
                ("Sequence", enrollment.get("sequence_name") or enrollment.get("sequence_id")),
                ("CRM target", enrollment.get("crm_target_summary")),
                ("Status", enrollment.get("status")),
                ("Current step", enrollment.get("current_step_order")),
                ("Next step", enrollment.get("next_step_at")),
                ("Pause reason", enrollment.get("pause_reason")),
            ],
        ),
        html.Div(_sequence_actions(enrollment, role), className="detail-actions"),
        html.Section(
            [
                html.H2("Workflow"),
                records_table(
                    [_sequence_step_row(step) for step in sequence.get("steps", [])],
                    [
                        ("Step", "step_order"),
                        ("Wait", "delay_display"),
                        ("Subject", "subject_template"),
                        ("Channel", "channel"),
                    ],
                ),
            ],
            className="detail-panel",
        ),
        records_table(
            enrollment.get("outbound_emails", []),
            [
                ("To", "to_email"),
                ("Subject", "subject"),
                ("Status", "status"),
                ("Scheduled", "scheduled_at"),
                ("Sent", "sent_at"),
            ],
        ),
        _sequence_alert_form(enrollment_id, role),
    ]
    return _page("Sequence Enrollment", [enrollment], children)


def sequence_definition_detail_page(
    client: ConsoleApiClient, sequence_id: str, *, role: str
) -> html.Div:
    sequence = _safe_get(client, f"/v1/sequences/{sequence_id}")
    children = [
        _sequence_edit_form(sequence, role),
        records_table(
            [_sequence_step_row(step) for step in sequence.get("steps", [])],
            [
                ("Step", "step_order"),
                ("Wait", "delay_display"),
                ("Subject", "subject_template"),
                ("Body", "body_template"),
                ("Active", "active"),
            ],
        ),
    ]
    return _page("Sequence Definition", [sequence], children)


def meetings_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div:
    payload = _safe_get(
        client,
        "/v1/reporting/meetings",
        _filtered(params, "status", "crm_sync_status", "cursor"),
    )
    children = [
        query_badges(params),
        records_table(
            payload.get("meetings", []),
            [
                ("Subject", "subject"),
                ("Status", "status"),
                ("Start", "start_at"),
                ("Calendar", "provider_event_id"),
                ("CRM sync", "crm_sync_status"),
                ("Outcome", "outcome_status"),
            ],
            actions=lambda record: [
                dcc.Link("Open", href=f"/meetings/{record.get('id')}", refresh=False)
            ],
        ),
        _pagination(payload, "/meetings", params),
    ]
    return _page("Meeting Handoff", [payload], children)


def meeting_detail_page(client: ConsoleApiClient, meeting_id: str, *, role: str) -> html.Div:
    payload = _safe_get(client, f"/v1/reporting/meetings/{meeting_id}")
    meeting = payload.get("meeting", {})
    children = [
        detail_panel(
            "Meeting detail",
            [
                ("Subject", meeting.get("subject")),
                ("Status", meeting.get("status")),
                ("Start", meeting.get("start_at")),
                ("End", meeting.get("end_at")),
                ("Timezone", meeting.get("timezone")),
                ("Attendees", meeting.get("attendees")),
                ("Calendar event", meeting.get("provider_event_id")),
                ("Calendar link", meeting.get("provider_html_link")),
                ("CRM sync", meeting.get("crm_sync_status")),
                ("CRM sync error", meeting.get("crm_sync_error")),
                ("Outcome", meeting.get("outcome_status")),
            ],
        ),
        html.Div(_meeting_actions(meeting, role), className="detail-actions"),
        detail_panel("Prep packet", [("Packet", meeting.get("prep_packet"))]),
        records_table(
            meeting.get("follow_up_tasks", []),
            [
                ("Title", "title"),
                ("Owner", "owner"),
                ("Due", "due_at"),
                ("Status", "status"),
                ("CRM sync", "crm_sync_status"),
            ],
        ),
    ]
    return _page("Meeting Detail", [payload], children)


def source_health_page(client: ConsoleApiClient, params: dict[str, Any]) -> html.Div:
    payload = _safe_get(
        client,
        "/v1/reporting/source-health",
        _filtered(params, "kind", "freshness_status", "cursor"),
    )
    children = [
        query_badges(params),
        records_table(
            payload.get("sources", []),
            [
                ("Source", "name"),
                ("Kind", "source_kind"),
                ("Adapter", "adapter_type"),
                ("Policy", "policy_state"),
                ("State", "operating_state"),
                ("Freshness", "freshness_status"),
                ("Lag", "freshness_lag_seconds"),
                ("Failures", "consecutive_failures"),
            ],
        ),
        html.Div(
            "Source pause, replay, and policy controls are read-only here until owning "
            "source-operations APIs are added.",
            className="operator-note",
        ),
        _pagination(payload, "/operations/sources", params),
    ]
    return _page("Source Health", [payload], children)


def _page(
    title: str,
    payloads: list[dict[str, Any] | None],
    children: list[Any],
    *,
    query_params: dict[str, Any] | None = None,
) -> html.Div:
    subtitle = "Filters are represented in the URL query string." if query_params else None
    return html.Div(
        [
            page_header(title, subtitle=subtitle),
            metadata_banner(payloads),
            *_payload_error_notices(payloads),
            html.Div(children, className="page-stack"),
        ],
        className="dashboard-page",
    )


def _safe_get(
    client: ConsoleApiClient,
    path: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_params = dict(params or {})
    if request_params and "limit" not in request_params:
        request_params["limit"] = REPORTING_LIMIT
    try:
        return client.get(path, params=request_params or None)
    except ConsoleApiError as exc:
        return {"_error": exc.to_dict()}


def _payload_error_notices(payloads: list[dict[str, Any] | None]) -> list[html.Div]:
    errors = []
    for payload in payloads:
        if not isinstance(payload, dict) or "_error" not in payload:
            continue
        error = payload["_error"]
        if not isinstance(error, dict):
            errors.append(error_notice("Gateway request failed", str(error)))
            continue
        status = error.get("status_code")
        path = error.get("path")
        detail_parts = []
        if path:
            detail_parts.append(f"Endpoint: {path}")
        if status:
            detail_parts.append(f"Status: {status}")
        message = error.get("message") or "Gateway request failed"
        detail = " · ".join(detail_parts) or "Check the gateway service and retry the page."
        errors.append(error_notice(str(message), detail))
    return errors


def _count(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    return len(value) if isinstance(value, list) else 0


def _params(search: str | None) -> dict[str, Any]:
    parsed = parse_qs((search or "").lstrip("?"))
    return {key: values[-1] for key, values in parsed.items() if values}


def _filtered(params: dict[str, Any], *allowed: str) -> dict[str, Any]:
    filtered = {key: params.get(key) for key in allowed}
    filtered["limit"] = params.get("limit") or REPORTING_LIMIT
    return filtered


def _pagination(payload: dict[str, Any], base_path: str, params: dict[str, Any]) -> html.Div:
    next_cursor = payload.get("next_cursor")
    if not next_cursor:
        return html.Div()
    next_params = {**params, "cursor": next_cursor}
    query = "&".join(
        f"{key}={value}" for key, value in next_params.items() if value not in (None, "")
    )
    return html.Div(
        dcc.Link("Next page", href=f"{base_path}?{query}", refresh=False),
        className="pagination",
    )


def _manual_event_form(role: str) -> html.Div:
    if not _can_mutate(role):
        return html.Div()
    return html.Div(
        [
            html.Div(
                html.Button(
                    [icon("plus"), html.Span("Add event")],
                    id="manual-event-open",
                    n_clicks=0,
                    className="icon-button",
                ),
                className="form-launcher",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H2("Add event"),
                            html.Div(
                                [
                                    dcc.Input(
                                        id="manual-event-name",
                                        placeholder="Event name",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-url",
                                        placeholder="Canonical URL",
                                        type="url",
                                    ),
                                    dcc.Input(
                                        id="manual-event-start",
                                        placeholder="UTC start",
                                        type="datetime-local",
                                    ),
                                    dcc.Dropdown(
                                        id="manual-event-format",
                                        value="in-person",
                                        clearable=False,
                                        searchable=False,
                                        options=[
                                            {"label": "In person", "value": "in-person"},
                                            {"label": "Online", "value": "online"},
                                            {"label": "Hybrid", "value": "hybrid"},
                                            {"label": "Unknown", "value": "unknown"},
                                        ],
                                    ),
                                    dcc.Input(
                                        id="manual-event-venue",
                                        placeholder="Venue",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-street",
                                        placeholder="Street address",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-city",
                                        placeholder="City",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-region",
                                        placeholder="Region",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-postcode",
                                        placeholder="Postcode",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-country",
                                        placeholder="Country",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-virtual-url",
                                        placeholder="Meeting URL",
                                        type="url",
                                    ),
                                    dcc.Input(
                                        id="manual-event-topics",
                                        placeholder="Topics, comma separated",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-source-items",
                                        placeholder="Source item IDs, comma separated",
                                        type="text",
                                    ),
                                ],
                                className="form-grid",
                            ),
                            html.Div(
                                [
                                    html.Button(
                                        [icon("check"), html.Span("Create")],
                                        id="manual-event-submit",
                                        n_clicks=0,
                                        className="icon-button",
                                    ),
                                    html.Button(
                                        [icon("x"), html.Span("Cancel")],
                                        id="manual-event-cancel",
                                        n_clicks=0,
                                        className="icon-button",
                                    ),
                                ],
                                className="modal-actions",
                            ),
                        ],
                        className="modal-panel wide",
                    )
                ],
                id="manual-event-modal",
                className="modal-backdrop hidden",
            ),
        ],
        className="toolbar-block",
    )


def _event_edit_modal(event: dict[str, Any], role: str) -> html.Div:
    if not _can_mutate(role) or not event.get("id"):
        return html.Div()
    return html.Div(
        [
            html.Div(
                html.Button(
                    [icon("edit-3"), html.Span("Edit event")],
                    id="event-edit-open",
                    n_clicks=0,
                    className="icon-button",
                ),
                className="form-launcher",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H2("Edit event"),
                            html.Div(
                                [
                                    dcc.Input(
                                        id="event-edit-name",
                                        value=event.get("name"),
                                        placeholder="Event name",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-url",
                                        value=event.get("canonical_url"),
                                        placeholder="Canonical URL",
                                        type="url",
                                    ),
                                    dcc.Input(
                                        id="event-edit-start",
                                        value=_datetime_local_value(event.get("starts_at_utc")),
                                        placeholder="UTC start",
                                        type="datetime-local",
                                    ),
                                    dcc.Dropdown(
                                        id="event-edit-format",
                                        value=event.get("event_format") or "unknown",
                                        clearable=False,
                                        searchable=False,
                                        options=[
                                            {"label": "In person", "value": "in-person"},
                                            {"label": "Online", "value": "online"},
                                            {"label": "Hybrid", "value": "hybrid"},
                                            {"label": "Unknown", "value": "unknown"},
                                        ],
                                    ),
                                    dcc.Input(
                                        id="event-edit-venue",
                                        value=event.get("venue_name"),
                                        placeholder="Venue",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-street",
                                        value=event.get("street_address"),
                                        placeholder="Street address",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-city",
                                        value=event.get("city"),
                                        placeholder="City",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-region",
                                        value=event.get("region"),
                                        placeholder="Region",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-postcode",
                                        value=event.get("postcode"),
                                        placeholder="Postcode",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-country",
                                        value=event.get("country"),
                                        placeholder="Country",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-virtual-url",
                                        value=event.get("virtual_url"),
                                        placeholder="Meeting URL",
                                        type="url",
                                    ),
                                    dcc.Input(
                                        id="event-edit-topics",
                                        value=", ".join(
                                            str(item) for item in event.get("topics") or []
                                        ),
                                        placeholder="Topics, comma separated",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-source-items",
                                        value=", ".join(
                                            str(item) for item in event.get("source_item_ids") or []
                                        ),
                                        placeholder="Source item IDs, comma separated",
                                        type="text",
                                    ),
                                ],
                                className="form-grid",
                            ),
                            html.Div(
                                [
                                    html.Button(
                                        [icon("save"), html.Span("Save")],
                                        id={
                                            "type": "event-edit-submit",
                                            "event_id": str(event.get("id") or ""),
                                            "version": event.get("version"),
                                        },
                                        n_clicks=0,
                                        className="icon-button",
                                    ),
                                    html.Button(
                                        [icon("x"), html.Span("Cancel")],
                                        id="event-edit-cancel",
                                        n_clicks=0,
                                        className="icon-button",
                                    ),
                                ],
                                className="modal-actions",
                            ),
                        ],
                        className="modal-panel wide",
                    )
                ],
                id="event-edit-modal",
                className="modal-backdrop hidden",
            ),
        ],
        className="toolbar-block",
    )


def _manual_incident_form(role: str) -> html.Div:
    if not _can_mutate(role):
        return html.Div()
    return html.Div(
        [
            html.Div(
                html.Button(
                    [icon("plus"), html.Span("Add incident")],
                    id="manual-incident-open",
                    n_clicks=0,
                    className="icon-button",
                ),
                className="form-launcher",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H2("Add incident"),
                            html.Div(
                                [
                                    dcc.Input(
                                        id="manual-incident-title",
                                        placeholder="Incident title",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-company",
                                        placeholder="Companies, comma separated",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-type",
                                        placeholder="Incident type",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-first-observed",
                                        placeholder="First observed",
                                        type="datetime-local",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-source-items",
                                        placeholder="Source item IDs, comma separated",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-domains",
                                        placeholder="Domains, comma separated",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-vector",
                                        placeholder="Attack vector",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-evidence-urls",
                                        placeholder="Evidence URLs, comma separated",
                                        type="text",
                                    ),
                                ],
                                className="form-grid",
                            ),
                            html.Div(
                                [
                                    html.Button(
                                        [icon("check"), html.Span("Create")],
                                        id="manual-incident-submit",
                                        n_clicks=0,
                                        className="icon-button",
                                    ),
                                    html.Button(
                                        [icon("x"), html.Span("Cancel")],
                                        id="manual-incident-cancel",
                                        n_clicks=0,
                                        className="icon-button",
                                    ),
                                ],
                                className="modal-actions",
                            ),
                        ],
                        className="modal-panel wide",
                    )
                ],
                id="manual-incident-modal",
                className="modal-backdrop hidden",
            ),
        ],
        className="toolbar-block",
    )


def _participant_enrich_form(event_id: str, role: str) -> html.Div:
    if not _can_mutate(role):
        return html.Div()
    return html.Section(
        [
            html.H2("Target enrichment"),
            html.Div(
                [
                    dcc.Input(
                        id={"type": "event-enrich-domain", "event_id": event_id},
                        placeholder="Company domain for selected participant",
                        type="text",
                    ),
                    html.Span(
                        "Use Enrich Target on a participant row after entering a domain.",
                        className="muted",
                    ),
                ],
                className="inline-form",
            ),
        ],
        className="detail-panel",
    )


def _event_calendar(events: list[dict[str, Any]]) -> html.Div:
    buckets = Counter(
        str(event.get("starts_at_utc") or event.get("original_start") or "unknown")[:10]
        for event in events
    )
    if not buckets:
        return empty_state("Calendar has no event dates for this filter.")
    figure = go.Figure(data=[go.Bar(x=list(buckets.keys()), y=list(buckets.values()))])
    figure.update_layout(margin={"l": 32, "r": 16, "t": 20, "b": 32}, height=240)
    return html.Section([html.H2("Calendar"), dcc.Graph(figure=figure)], className="chart-panel")


def _event_map(events: list[dict[str, Any]]) -> html.Div:
    points = [
        event
        for event in events
        if event.get("latitude") is not None and event.get("longitude") is not None
    ]
    if not points:
        return empty_state("Map view needs geocoded event addresses.")
    figure = go.Figure(
        data=[
            go.Scattergeo(
                lat=[point.get("latitude") for point in points],
                lon=[point.get("longitude") for point in points],
                text=[_event_hover_text(point) for point in points],
                mode="markers",
                marker={"size": 11, "color": "#0f766e", "line": {"width": 1, "color": "#ffffff"}},
                hovertemplate="%{text}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        height=460,
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        showlegend=False,
        geo={
            "projection_type": "natural earth",
            "showland": True,
            "landcolor": "#eef2f7",
            "countrycolor": "#cbd5e1",
            "showocean": True,
            "oceancolor": "#e0f2fe",
        },
    )
    return html.Section(
        [html.H2("Event map"), dcc.Graph(figure=figure)], className="chart-panel event-map-panel"
    )


def _incident_chart(incidents: list[dict[str, Any]]) -> html.Div:
    buckets = Counter(str(incident.get("status") or "unknown") for incident in incidents)
    if not buckets:
        return empty_state("No incident status data for this filter.")
    figure = go.Figure(data=[go.Bar(x=list(buckets.keys()), y=list(buckets.values()))])
    figure.update_layout(margin={"l": 32, "r": 16, "t": 20, "b": 32}, height=220)
    return html.Section(
        [html.H2("Incident Status"), dcc.Graph(figure=figure)],
        className="chart-panel",
    )


def _review_actions(record: dict[str, Any], role: str) -> list[Any]:
    disabled = not _can_mutate(role)
    return [
        action_button(
            "Approve",
            _action_id(
                "review",
                "approve",
                record.get("id"),
                record.get("version"),
                record.get("policy_snapshot_hash"),
            ),
            "check",
            disabled=disabled,
        ),
        action_button(
            "Reject",
            _action_id(
                "review",
                "reject",
                record.get("id"),
                record.get("version"),
                record.get("policy_snapshot_hash"),
            ),
            "x",
            disabled=disabled,
            danger=True,
        ),
    ]


def _bulk_review_actions(records: list[dict[str, Any]], role: str) -> list[Any]:
    if not records:
        return []
    versions = {
        str(record.get("id")): record.get("version") for record in records if record.get("id")
    }
    target_ids = ",".join(versions.keys())
    disabled = not _can_mutate(role)
    return [
        action_button(
            "Bulk approve visible",
            _action_id("bulk-review", "approve", target_ids, versions),
            "list-checks",
            disabled=disabled,
        ),
        action_button(
            "Bulk reject visible",
            _action_id("bulk-review", "reject", target_ids, versions),
            "list-x",
            disabled=disabled,
            danger=True,
        ),
    ]


def _crm_target_actions(record: dict[str, Any], role: str) -> list[Any]:
    return [
        action_button(
            "Export",
            _action_id("crm-export", "start", record.get("id"), record.get("version")),
            "upload",
            disabled=not _can_mutate(role),
        )
    ]


def _crm_batch_actions(batch: dict[str, Any], role: str) -> list[Any]:
    return [
        action_button(
            "Retry failed",
            _action_id("crm-retry", "retry", batch.get("id")),
            "rotate-ccw",
            disabled=not _can_mutate(role),
        )
    ]


def _participant_actions(record: dict[str, Any], role: str) -> list[Any]:
    queued = bool(record.get("enrichment_queued"))
    return [
        action_button(
            "Queued" if queued else "Add to Enrichment Queue",
            _action_id("event-participant", "enrich", record.get("id")),
            "check-circle" if queued else "sparkles",
            disabled=queued or not _can_mutate(role),
        )
    ]


def _incident_actions(record: dict[str, Any], role: str, *, include_open: bool = True) -> list[Any]:
    disabled = not _can_mutate(role)
    version_missing = record.get("version") is None
    status = str(record.get("status") or "")
    actions: list[Any] = []
    if include_open:
        actions.append(
            dcc.Link(
                "Open",
                href=f"/incidents/{record.get('id')}",
                refresh=False,
                className="text-link",
            )
        )
    actions.extend(
        [
            action_button(
                "Add to Watchlist",
                _action_id("incident", "promote", record.get("id"), record.get("version")),
                "radar",
                disabled=disabled or version_missing or status != "corroborated",
            ),
            action_button(
                "Revert" if status == "corroborated" else "Corroborate",
                _action_id(
                    "incident",
                    "revert" if status == "corroborated" else "corroborate",
                    record.get("id"),
                    record.get("version"),
                ),
                "undo-2" if status == "corroborated" else "badge-check",
                disabled=disabled or version_missing,
            ),
            action_button(
                "Reject",
                _action_id("incident", "reject", record.get("id"), record.get("version")),
                "x",
                disabled=disabled or version_missing,
                danger=True,
            ),
        ]
    )
    return actions


def _watch_actions(record: dict[str, Any], role: str) -> list[Any]:
    next_enabled = not bool(record.get("enabled"))
    return [
        action_button(
            "Enable" if next_enabled else "Pause",
            _action_id(
                "watch",
                "toggle",
                record.get("id"),
                record.get("version"),
                enabled=next_enabled,
            ),
            "play" if next_enabled else "pause",
            disabled=not _can_mutate(role),
        )
    ]


def _sequence_actions(record: dict[str, Any], role: str) -> list[Any]:
    disabled = not _can_mutate(role)
    status = str(record.get("status") or "")
    actions = [
        dcc.Link(
            "Open",
            href=f"/sequences/enrollments/{record.get('id')}",
            refresh=False,
            className="text-link",
        ),
        action_button(
            "Pause",
            _action_id("sequence", "pause", record.get("id")),
            "pause",
            disabled=disabled,
        ),
        action_button(
            "Resume",
            _action_id("sequence", "resume", record.get("id")),
            "play",
            disabled=disabled or status != "paused",
        ),
        action_button(
            "Cancel",
            _action_id("sequence", "cancel", record.get("id")),
            "x",
            disabled=disabled,
            danger=True,
        ),
    ]
    return actions


def _sequence_pause_modal() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H2("Pause sequence"),
                    html.Label("Reason", htmlFor="sequence-pause-reason"),
                    dcc.Textarea(
                        id="sequence-pause-reason",
                        placeholder="Why should this enrollment be paused?",
                    ),
                    html.Div(
                        [
                            html.Button(
                                [icon("check"), html.Span("Confirm")],
                                id="sequence-pause-confirm",
                                n_clicks=0,
                                className="icon-button",
                            ),
                            html.Button(
                                [icon("x"), html.Span("Cancel")],
                                id="sequence-pause-cancel",
                                n_clicks=0,
                                className="icon-button",
                            ),
                        ],
                        className="detail-actions",
                    ),
                ],
                className="modal-panel",
            )
        ],
        id="sequence-pause-modal",
        className="modal-backdrop hidden",
    )


def _sequence_enrollment_row(enrollment: dict[str, Any]) -> dict[str, Any]:
    return {
        **enrollment,
        "contact_name": enrollment.get("contact_name") or enrollment.get("contact_id"),
        "account_name": enrollment.get("account_name")
        or enrollment.get("account_domain")
        or enrollment.get("account_id"),
        "sequence_name": enrollment.get("sequence_name") or enrollment.get("sequence_id"),
    }


def _sequence_row(sequence: dict[str, Any]) -> dict[str, Any]:
    return {**sequence, "step_count": len(sequence.get("steps") or [])}


def _sequence_step_row(step: dict[str, Any]) -> dict[str, Any]:
    return {**step, "delay_display": format_duration(step.get("delay_seconds"))}


def _sequence_alert_form(enrollment_id: str, role: str) -> html.Div:
    if not _can_mutate(role):
        return html.Div()
    return html.Section(
        [
            html.H2("Reminder alert"),
            html.Div(
                [
                    dcc.Input(
                        id={"type": "sequence-alert-recipient", "enrollment_id": enrollment_id},
                        placeholder="Recipient email",
                        type="email",
                    ),
                    dcc.Input(
                        id={"type": "sequence-alert-subject", "enrollment_id": enrollment_id},
                        placeholder="Subject",
                        type="text",
                    ),
                    dcc.Textarea(
                        id={"type": "sequence-alert-body", "enrollment_id": enrollment_id},
                        placeholder="Reminder body",
                    ),
                    html.Button(
                        [icon("bell"), html.Span("Create alert")],
                        id={"type": "sequence-alert-submit", "enrollment_id": enrollment_id},
                        n_clicks=0,
                        className="icon-button",
                    ),
                ],
                className="form-grid",
            ),
        ],
        className="detail-panel",
    )


def _sequence_edit_form(sequence: dict[str, Any], role: str) -> html.Div:
    if not _can_mutate(role):
        return detail_panel(
            "Sequence",
            [
                ("Name", sequence.get("name")),
                ("Owner", sequence.get("owner_id")),
                ("Status", sequence.get("status")),
                ("Rate limits", sequence.get("rate_limit_policy")),
            ],
        )
    return html.Section(
        [
            html.H2("Edit sequence"),
            html.Div(
                [
                    dcc.Input(
                        id="sequence-edit-name",
                        value=sequence.get("name"),
                        placeholder="Name",
                        type="text",
                    ),
                    dcc.Input(
                        id="sequence-edit-owner",
                        value=sequence.get("owner_id"),
                        placeholder="Owner",
                        type="text",
                    ),
                    dcc.Dropdown(
                        id="sequence-edit-status",
                        value=sequence.get("status"),
                        options=[
                            {"label": "Active", "value": "active"},
                            {"label": "Paused", "value": "paused"},
                            {"label": "Archived", "value": "archived"},
                        ],
                        clearable=False,
                    ),
                    dcc.Textarea(
                        id="sequence-edit-steps",
                        value=json.dumps(sequence.get("steps") or [], indent=2, default=str),
                    ),
                    html.Button(
                        [icon("save"), html.Span("Save sequence")],
                        id={
                            "type": "sequence-edit-submit",
                            "sequence_id": str(sequence.get("id") or ""),
                        },
                        n_clicks=0,
                        className="icon-button",
                    ),
                ],
                className="form-grid",
            ),
        ],
        className="detail-panel",
    )


def _contact_queue_row(candidate: dict[str, Any]) -> dict[str, Any]:
    payload = candidate.get("candidate_payload") or {}
    verified_email = payload.get("verified_email")
    status = payload.get("verified_email_status")
    verified_display = (
        f"{verified_email} ({status})" if verified_email and status else verified_email
    )
    return {
        **candidate,
        "provenance": _provenance_label(candidate),
        "verified_email": verified_display,
    }


def _provenance_label(candidate: dict[str, Any]) -> str:
    origin = str(candidate.get("origin_type") or "")
    payload = candidate.get("candidate_payload") or {}
    if origin == "event_participant":
        return "Global events"
    if origin == "security_incident":
        return "Global incidents"
    if origin == "manual":
        actor = payload.get("created_by") or "unknown"
        return f"Manual by {actor}"
    return human_label(origin) if origin else "-"


def _meeting_actions(record: dict[str, Any], role: str) -> list[Any]:
    disabled = not _can_mutate(role)
    return [
        action_button(
            "Prep packet",
            _action_id("meeting", "prep", record.get("id")),
            "file-text",
            disabled=disabled,
        ),
        action_button(
            "Record outcome",
            _action_id("meeting", "outcome", record.get("id")),
            "clipboard-check",
            disabled=disabled,
        ),
        action_button(
            "Retry CRM",
            _action_id("meeting", "retry-sync", record.get("id")),
            "rotate-ccw",
            disabled=disabled,
        ),
        action_button(
            "Cancel",
            _action_id("meeting", "cancel", record.get("id")),
            "x",
            disabled=disabled,
            danger=True,
        ),
    ]


def _participant_rows(
    participants: list[dict[str, Any]],
    contact_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    queued_origin_ids = {
        str(candidate.get("origin_id"))
        for candidate in contact_candidates
        if candidate.get("origin_id")
    }
    return [
        {
            **participant,
            "enrichment_queued": str(participant.get("id")) in queued_origin_ids,
        }
        for participant in participants
    ]


def _incident_table_row(incident: dict[str, Any]) -> dict[str, Any]:
    companies = incident.get("affected_companies") or [incident.get("primary_affected_company")]
    evidence = [
        *(incident.get("evidence_families") or []),
        *(incident.get("evidence_urls") or []),
    ]
    return {
        **incident,
        "company_display": _inline_list(companies),
        "evidence_display": _inline_list(evidence),
    }


def _inline_list(value: Any) -> str:
    if value in (None, ""):
        return "-"
    if isinstance(value, list):
        values = [str(item) for item in value if item not in (None, "")]
        return ", ".join(values) if values else "-"
    return str(value)


def _address(event: dict[str, Any]) -> str:
    locality = " ".join(str(part) for part in (event.get("postcode"), event.get("city")) if part)
    parts = [
        event.get("street_address"),
        locality,
        event.get("region"),
        event.get("country"),
    ]
    return ", ".join(str(part) for part in parts if part) or "-"


def _event_hover_text(event: dict[str, Any]) -> str:
    rows = [str(event.get("name") or "Event")]
    address = _address(event)
    if address != "-":
        rows.append(address)
    display_name = event.get("geocode_display_name")
    if display_name:
        rows.append(str(display_name))
    return "<br>".join(rows)


def _datetime_local_value(value: Any) -> str | None:
    if not value:
        return None
    text = str(value)
    if "T" not in text:
        return text
    return text[:16]


def _action_id(
    kind: str,
    action: str,
    target_id: Any,
    version: Any = None,
    policy_hash: Any = None,
    enabled: Any = None,
) -> dict[str, Any]:
    return {
        "type": "dashboard-action",
        "kind": kind,
        "action": action,
        "target_id": str(target_id or ""),
        "version": _action_value(version),
        "policy_hash": policy_hash or "",
        "enabled": enabled if enabled is not None else "",
    }


def _action_value(value: Any) -> str | int | float | bool:
    if value is None:
        return ""
    if isinstance(value, str | int | float | bool):
        return value
    return json.dumps(value, sort_keys=True, default=str)


def _can_mutate(role: str) -> bool:
    return role in {
        DashboardRole.ANALYST.value,
        DashboardRole.GOVERNANCE_REVIEWER.value,
        DashboardRole.ADMINISTRATOR.value,
    }


def _normalize_role(role: str | None) -> str:
    try:
        return DashboardRole(role or DashboardRole.VIEWER.value).value
    except ValueError:
        return DashboardRole.VIEWER.value


def _location(event: dict[str, Any]) -> str:
    parts = [event.get("venue_name"), event.get("city"), event.get("region"), event.get("country")]
    return ", ".join(str(part) for part in parts if part)
