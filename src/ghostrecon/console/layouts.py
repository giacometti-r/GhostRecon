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
    render_inline_value,
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
SEQUENCE_LAYER_COUNT = 20


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
        if path.startswith("/watchlists/"):
            return watchlist_detail_page(api, path.rsplit("/", 1)[-1], role=context_role)
        if path == "/review/enrichment":
            return enrichment_review_page(api, params, role=context_role)
        if path == "/review":
            return review_page(api, params, role=context_role)
        if path.startswith("/review/"):
            return review_detail_page(api, path.rsplit("/", 1)[-1], role=context_role)
        if path == "/crm/exports":
            return crm_exports_page(api, params, role=context_role)
        if path.startswith("/crm/exports/targets/"):
            return crm_target_detail_page(api, path.rsplit("/", 1)[-1], role=context_role)
        if path.startswith("/crm/exports/"):
            return crm_export_detail_page(api, path.rsplit("/", 1)[-1], role=context_role)
        if path == "/sequences":
            return sequences_page(api, params, role=context_role)
        if path == "/sequences/definitions":
            return sequence_definitions_page(api, params, role=context_role)
        if path.startswith("/sequences/enrollments/"):
            return sequence_enrollment_detail_page(api, path.rsplit("/", 1)[-1], role=context_role)
        if path.startswith("/sequences/activities/"):
            return sequence_activity_detail_page(api, path.rsplit("/", 1)[-1], role=context_role)
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
        _filter_panel(
            "/events",
            params,
            [
                ("series", "Series"),
                ("source", "Source"),
                ("country", "Country"),
                ("event_format", "Format"),
                ("topic", "Topic"),
            ],
        ),
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
        _event_participant_form(event.get("id") or event_id, role),
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
        _filter_panel(
            "/incidents",
            params,
            [
                ("status", "Status"),
                ("source", "Source"),
                ("company", "Company"),
                ("attack_vector", "Attack vector"),
                ("incident_type", "Incident type"),
            ],
        ),
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
        _incident_edit_modal(incident, role),
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
    columns = [
        ("Company", "display_name"),
        ("Owner", "owner"),
        ("Monitoring", "monitoring_status"),
        ("Last run", "last_monitored_at"),
        ("Next run", "next_monitoring_at"),
    ]
    if role == DashboardRole.GOVERNANCE_REVIEWER.value:
        columns.append(("Origin incident", "origin_incident_id"))
    children = [
        query_badges(params),
        _filter_panel(
            "/watchlists",
            params,
            [
                ("target_type", "Type"),
                ("enabled", "Enabled"),
                ("owner", "Owner"),
            ],
        ),
        records_table(
            payload.get("watch_targets", []),
            columns,
            actions=lambda record: _watch_actions(record, role),
        ),
        _pagination(payload, "/watchlists", params),
    ]
    return _page("Watchlists", [payload], children)


def watchlist_detail_page(client: ConsoleApiClient, watch_target_id: str, *, role: str) -> html.Div:
    payload = _safe_get(client, f"/v1/reporting/watch-targets/{watch_target_id}")
    target = payload.get("watch_target", {})
    rows = [
        ("Company", target.get("display_name")),
        ("Owner", target.get("owner")),
        ("Monitoring", target.get("monitoring_status")),
        ("Enabled", target.get("monitoring_enabled")),
        ("Last run", target.get("last_monitored_at")),
        ("Next run", target.get("next_monitoring_at")),
        ("Last error", target.get("monitoring_error")),
    ]
    if role == DashboardRole.GOVERNANCE_REVIEWER.value:
        rows.append(("Origin incident", target.get("origin_incident_id")))
    children = [
        detail_panel("Watchlist Item", rows),
        html.Div(_watch_actions(target, role, include_open=False), className="detail-actions"),
        detail_panel("Monitoring summary", [("Summary", target.get("monitoring_summary"))]),
        metadata_details(payload)
        if role == DashboardRole.GOVERNANCE_REVIEWER.value
        else html.Div(),
    ]
    return _page("Watchlist Item", [payload], children)


def review_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div:
    payload = _safe_get(
        client,
        "/v1/reporting/review-queue",
        _filtered(params, "status", "candidate_type", "target_type", "cursor"),
    )
    children = [
        query_badges(params),
        _filter_panel(
            "/review",
            params,
            [
                ("status", "Status"),
                ("candidate_type", "Candidate type"),
                ("target_type", "Target type"),
            ],
        ),
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
            [_review_queue_row(candidate) for candidate in payload.get("candidates", [])],
            [
                ("Name", "name"),
                ("Company", "company"),
                ("Domain", "domain"),
                ("Email", "email"),
                ("Date added", "created_at"),
            ],
            actions=lambda record: _review_actions(record, role),
        ),
        _pagination(payload, "/review", params),
    ]
    return _page("Analyst Review", [payload], children)


def enrichment_review_page(
    client: ConsoleApiClient, params: dict[str, Any], *, role: str
) -> html.Div:
    contacts = _safe_get(client, "/v1/enrichment/contact-candidates", _filtered(params, "status"))
    cases = _safe_get(client, "/v1/enrichment/entity-resolutions", _filtered(params, "status"))
    contact_rows = [_contact_queue_row(candidate) for candidate in contacts.get("candidates", [])]
    children = [
        html.Div(
            _bulk_contact_queue_actions(contact_rows, role),
            className="bulk-actions",
        ),
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
            actions=lambda record: _contact_queue_actions(record, role),
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


def review_detail_page(client: ConsoleApiClient, candidate_id: str, *, role: str) -> html.Div:
    candidate = _safe_get(client, f"/v1/review/candidates/{candidate_id}")
    row = _review_queue_row(candidate)
    children = [
        detail_panel(
            "Review candidate",
            [
                ("Name", row.get("name")),
                ("Company", row.get("company")),
                ("Domain", row.get("domain")),
                ("Email", row.get("email")),
                ("Reason", candidate.get("reason") or candidate.get("reason_code")),
                ("Status", candidate.get("status")),
                ("Date added", candidate.get("created_at")),
            ],
        ),
        _review_edit_panel(row, role),
        html.Div(_review_actions(candidate, role), className="detail-actions"),
    ]
    return _page("Review Candidate", [candidate], children)


def crm_exports_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div:
    payload = _safe_get(
        client,
        "/v1/reporting/crm-targets",
        {
            **_filtered(params, "status", "target_type", "export_status", "cursor"),
            "target_type": params.get("target_type") or "email_candidate",
        },
    )
    children = [
        query_badges(params),
        _filter_panel(
            "/crm/exports",
            params,
            [
                ("status", "Status"),
                ("target_type", "Target type"),
                ("export_status", "Export status"),
            ],
        ),
        records_table(
            [_crm_target_row(target) for target in payload.get("crm_targets", [])],
            [
                ("Name", "name"),
                ("Company", "company"),
                ("Email", "email"),
                ("Status", "status"),
                ("Export", "export_status"),
                ("Date added", "created_at"),
            ],
            actions=lambda record: _crm_target_actions(record, role),
        ),
        _pagination(payload, "/crm/exports", params),
    ]
    return _page("CRM Targets and Export", [payload], children)


def crm_target_detail_page(client: ConsoleApiClient, crm_target_id: str, *, role: str) -> html.Div:
    payload = _safe_get(client, f"/v1/reporting/crm-targets/{crm_target_id}")
    target = payload.get("crm_target", {})
    row = _crm_target_row(target)
    children = [
        detail_panel(
            "CRM Target",
            [
                ("Name", row.get("name")),
                ("Company", row.get("company")),
                ("Email", row.get("email")),
                ("Status", target.get("status")),
                ("Export", target.get("export_status")),
                ("Target type", target.get("target_type")),
                ("Date added", target.get("created_at")),
            ],
        ),
        _crm_target_edit_panel(row, role),
        html.Div(_crm_target_actions(target, role), className="detail-actions"),
    ]
    return _page("CRM Target", [payload], children)


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
    activities = _safe_get(client, "/v1/sequences/activities", {"limit": REPORTING_LIMIT})
    children = [
        query_badges(params),
        _filter_panel(
            "/sequences",
            params,
            [
                ("status", "Enrollment status"),
            ],
        ),
        html.Div(
            [
                dcc.Link(
                    [icon("list-plus"), html.Span("Sequence Definitions")],
                    href="/sequences/definitions",
                    refresh=False,
                    className="icon-button link-button",
                )
            ],
            className="detail-actions",
        ),
        html.Section(
            [
                html.H2("Sequence activities"),
                records_table(
                    [
                        _sequence_activity_row(activity)
                        for activity in activities.get("activities", [])
                    ],
                    [
                        ("Prospect", "contact_name"),
                        ("Company", "account_name"),
                        ("Channel", "channel"),
                        ("Status", "status"),
                        ("Due", "due_at"),
                        ("Step", "step_order"),
                    ],
                    actions=lambda record: _sequence_activity_actions(record, role),
                    empty_message="No pending sequence activities.",
                ),
            ],
            className="detail-panel",
        ),
        records_table(
            [
                _sequence_enrollment_row(enrollment)
                for enrollment in payload.get("enrollments", [])
                if params.get("status") or enrollment.get("status") not in {"canceled", "completed"}
            ],
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
    return _page("Sequence State", [payload, activities], children)


def sequence_definitions_page(
    client: ConsoleApiClient, params: dict[str, Any], *, role: str
) -> html.Div:
    sequences = _safe_get(client, "/v1/sequences", {"limit": REPORTING_LIMIT})
    children = [
        query_badges(params),
        _sequence_create_form(role),
        records_table(
            [
                _sequence_row(sequence)
                for sequence in sequences.get("sequences", [])
                if sequence.get("status") != "archived"
            ],
            [
                ("Name", "name"),
                ("Owner", "owner_id"),
                ("Status", "status"),
                ("Version", "definition_version"),
                ("Channels", "channels"),
                ("Steps", "step_count"),
            ],
            actions=lambda record: [
                dcc.Link(
                    "Open",
                    href=f"/sequences/definitions/{record.get('id')}",
                    refresh=False,
                ),
                action_button(
                    "Delete",
                    _action_id("sequence-definition", "delete", record.get("id")),
                    "trash-2",
                    disabled=not _can_mutate(role),
                    danger=True,
                ),
            ],
        ),
    ]
    return _page("Sequence Definitions", [sequences], children)


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
                        ("Approval", "requires_approval"),
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


def sequence_activity_detail_page(
    client: ConsoleApiClient, activity_id: str, *, role: str
) -> html.Div:
    activity = _safe_get(client, f"/v1/sequences/activities/{activity_id}")
    metadata = activity.get("metadata") if isinstance(activity.get("metadata"), dict) else {}
    children = [
        detail_panel(
            "Sequence Activity",
            [
                ("Prospect", activity.get("contact_name")),
                ("Company", activity.get("account_name")),
                ("Email", activity.get("contact_email")),
                ("Sequence", activity.get("sequence_name")),
                ("Channel", activity.get("channel")),
                ("Status", activity.get("status")),
                ("Due", activity.get("due_at")),
            ],
        ),
        _sequence_activity_email_panel(activity, role),
        detail_panel("Activity metadata", [("Metadata", metadata)]),
        html.Div(_sequence_activity_actions(activity, role), className="detail-actions"),
    ]
    return _page("Sequence Activity", [activity], children)


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
                ("Channel", "channel"),
                ("Wait", "delay_display"),
                ("Subject", "subject_template"),
                ("Instructions", "instruction_summary"),
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
                ("Attendees", _attendees_display(meeting.get("attendees"))),
                ("Calendar event", meeting.get("provider_event_id")),
                ("Calendar link", meeting.get("provider_html_link")),
                ("CRM sync", meeting.get("crm_sync_status")),
                ("CRM sync error", meeting.get("crm_sync_error")),
                ("Outcome", meeting.get("outcome_status")),
            ],
        ),
        html.Div(_meeting_actions(meeting, role), className="detail-actions"),
        _prep_packet_panel(meeting.get("prep_packet")),
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


def _filter_panel(
    action: str,
    params: dict[str, Any],
    fields: list[tuple[str, str]],
) -> html.Form:
    return html.Form(
        [
            html.Div(
                [
                    html.Label(label, htmlFor=f"filter-{key}"),
                    dcc.Input(
                        id=f"filter-{key}",
                        name=key,
                        value=str(params.get(key) or ""),
                        type="text",
                    ),
                ],
                className="filter-field",
            )
            for key, label in fields
        ]
        + [
            html.Button(
                [icon("filter"), html.Span("Apply")], type="submit", className="icon-button"
            ),
            dcc.Link("Clear", href=action, refresh=False, className="text-link"),
        ],
        action=action,
        method="get",
        className="filter-panel",
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


def _incident_edit_modal(incident: dict[str, Any], role: str) -> html.Div:
    if not _can_mutate(role) or not incident.get("id"):
        return html.Div()
    return html.Section(
        [
            html.H2("Edit incident"),
            html.Div(
                [
                    dcc.Input(
                        id="incident-edit-title",
                        value=incident.get("title"),
                        placeholder="Title",
                        type="text",
                    ),
                    dcc.Input(
                        id="incident-edit-company",
                        value=_inline_list(incident.get("affected_companies")),
                        placeholder="Companies",
                        type="text",
                    ),
                    dcc.Input(
                        id="incident-edit-domains",
                        value=_inline_list(incident.get("affected_domains")),
                        placeholder="Domains",
                        type="text",
                    ),
                    dcc.Input(
                        id="incident-edit-type",
                        value=incident.get("incident_type"),
                        placeholder="Type",
                        type="text",
                    ),
                    dcc.Input(
                        id="incident-edit-vector",
                        value=incident.get("attack_vector"),
                        placeholder="Attack vector",
                        type="text",
                    ),
                    dcc.Input(
                        id="incident-edit-first-observed",
                        value=_datetime_local_value(incident.get("first_observed_at")),
                        placeholder="First observed",
                        type="datetime-local",
                    ),
                    dcc.Input(
                        id="incident-edit-evidence-urls",
                        value=_inline_list(incident.get("evidence_urls")),
                        placeholder="Evidence URLs",
                        type="text",
                    ),
                    html.Button(
                        [icon("save"), html.Span("Save incident")],
                        id={
                            "type": "incident-edit-submit",
                            "incident_id": str(incident.get("id") or ""),
                            "version": incident.get("version"),
                        },
                        n_clicks=0,
                        className="icon-button",
                    ),
                ],
                className="form-grid compact-form",
            ),
        ],
        className="detail-panel",
    )


def _participant_enrich_form(event_id: str, role: str) -> html.Div:
    return html.Div()


def _event_participant_form(event_id: str, role: str) -> html.Div:
    if not _can_mutate(role):
        return html.Div()
    return html.Section(
        [
            html.H2("Add participant"),
            html.Div(
                [
                    dcc.Input(
                        id={"type": "event-participant-name", "event_id": event_id},
                        placeholder="Name",
                        type="text",
                    ),
                    dcc.Input(
                        id={"type": "event-participant-org", "event_id": event_id},
                        placeholder="Organization",
                        type="text",
                    ),
                    dcc.Input(
                        id={"type": "event-participant-role", "event_id": event_id},
                        placeholder="Role",
                        type="text",
                    ),
                    dcc.Dropdown(
                        id={"type": "event-participant-type", "event_id": event_id},
                        value="speaker",
                        clearable=False,
                        options=[
                            {"label": "Speaker", "value": "speaker"},
                            {"label": "Sponsor", "value": "sponsor"},
                            {"label": "Organizer", "value": "organizer"},
                            {"label": "Attendee", "value": "attendee"},
                        ],
                    ),
                    dcc.Input(
                        id={"type": "event-participant-profile", "event_id": event_id},
                        placeholder="Profile URL",
                        type="url",
                    ),
                    html.Button(
                        [icon("plus"), html.Span("Add participant")],
                        id={"type": "event-participant-submit", "event_id": event_id},
                        n_clicks=0,
                        className="icon-button",
                    ),
                ],
                className="form-grid compact-form",
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
        dcc.Link(
            "Open",
            href=f"/review/{record.get('id')}",
            refresh=False,
            className="text-link",
        ),
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
        ),
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


def _contact_queue_actions(record: dict[str, Any], role: str) -> list[Any]:
    missing_domain = not bool(record.get("domain"))
    return [
        action_button(
            "Discover Domain",
            _action_id("contact-candidate", "discover-domain", record.get("id")),
            "globe",
            disabled=not missing_domain or not _can_mutate(role),
        ),
        action_button(
            "Find Email",
            _action_id("contact-candidate", "discover-email", record.get("id")),
            "mail-search",
            disabled=not _can_mutate(role),
        ),
    ]


def _bulk_contact_queue_actions(records: list[dict[str, Any]], role: str) -> list[Any]:
    if not records:
        return []
    target_ids = ",".join(str(record.get("id")) for record in records if record.get("id"))
    disabled = not _can_mutate(role)
    return [
        action_button(
            "Bulk Discover Domain",
            _action_id("bulk-contact-candidate", "discover-domain", target_ids),
            "globe-2",
            disabled=disabled,
        ),
        action_button(
            "Bulk Discover Email",
            _action_id("bulk-contact-candidate", "discover-email", target_ids),
            "mail-search",
            disabled=disabled,
        ),
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
                _action_id(
                    "incident",
                    "promote",
                    record.get("id"),
                    record.get("version"),
                    enabled=status,
                ),
                "radar",
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


def _watch_actions(record: dict[str, Any], role: str, *, include_open: bool = True) -> list[Any]:
    next_enabled = not bool(record.get("enabled"))
    actions: list[Any] = []
    if include_open:
        actions.append(
            dcc.Link(
                "Open",
                href=f"/watchlists/{record.get('id')}",
                refresh=False,
                className="text-link",
            )
        )
    actions.extend(
        [
            action_button(
                "Find Contact",
                _action_id("watch", "find-contact", record.get("id")),
                "search",
                disabled=not _can_mutate(role),
            ),
            action_button(
                "Enable Monitoring" if next_enabled else "Pause Monitoring",
                _action_id(
                    "watch",
                    "toggle",
                    record.get("id"),
                    record.get("version"),
                    enabled=next_enabled,
                ),
                "play" if next_enabled else "pause",
                disabled=not _can_mutate(role),
            ),
        ]
    )
    return actions


def _sequence_actions(record: dict[str, Any], role: str) -> list[Any]:
    disabled = not _can_mutate(role)
    status = str(record.get("status") or "")
    terminal = status in {"completed", "canceled", "suppressed", "failed"}
    toggle_action = "resume" if status == "paused" else "pause"
    toggle_label = "Resume" if status == "paused" else "Pause"
    toggle_icon = "play" if status == "paused" else "pause"
    actions = [
        dcc.Link(
            "Open",
            href=f"/sequences/enrollments/{record.get('id')}",
            refresh=False,
            className="text-link",
        ),
        action_button(
            toggle_label,
            _action_id("sequence", toggle_action, record.get("id")),
            toggle_icon,
            disabled=disabled or terminal,
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
    channels = sorted({str(step.get("channel") or "email") for step in sequence.get("steps") or []})
    return {
        **sequence,
        "step_count": len(sequence.get("steps") or []),
        "channels": ", ".join(channels) or "-",
    }


def _sequence_step_row(step: dict[str, Any]) -> dict[str, Any]:
    metadata = step.get("step_metadata") if isinstance(step.get("step_metadata"), dict) else {}
    instruction = (
        metadata.get("instructions")
        or metadata.get("call_script")
        or metadata.get("meeting_subject")
        or step.get("body_template")
        or "-"
    )
    return {
        **step,
        "delay_display": format_duration(step.get("delay_seconds")),
        "instruction_summary": instruction,
    }


def _sequence_activity_row(activity: dict[str, Any]) -> dict[str, Any]:
    return {
        **activity,
        "contact_name": activity.get("contact_name") or activity.get("contact_email") or "-",
        "account_name": activity.get("account_name") or "-",
    }


def _sequence_activity_actions(record: dict[str, Any], role: str) -> list[Any]:
    disabled = not _can_mutate(role)
    channel = str(record.get("channel") or "")
    status = str(record.get("status") or "")
    actions = [
        dcc.Link(
            "Open",
            href=f"/sequences/activities/{record.get('id')}",
            refresh=False,
            className="text-link",
        )
    ]
    if channel == "email":
        actions.append(
            action_button(
                "Approve",
                _action_id("sequence-activity", "approve-email", record.get("id")),
                "send",
                disabled=disabled or status not in {"pending_approval", "approved"},
            )
        )
    if channel == "call":
        actions.append(
            action_button(
                "Complete",
                _action_id("sequence-activity", "complete", record.get("id")),
                "check",
                disabled=disabled or status != "pending",
            )
        )
    if channel == "google_meet":
        actions.append(
            action_button(
                "Schedule",
                _action_id("sequence-activity", "schedule-meeting", record.get("id")),
                "calendar-plus",
                disabled=disabled or status != "pending",
            )
        )
    return actions


def _sequence_activity_email_panel(activity: dict[str, Any], role: str) -> html.Div:
    metadata = activity.get("metadata") if isinstance(activity.get("metadata"), dict) else {}
    if activity.get("channel") != "email":
        return html.Div()
    subject = metadata.get("subject") or metadata.get("subject_template") or "Following up"
    body = (
        metadata.get("body")
        or metadata.get("body_template")
        or ("Hi, sharing a concise security follow-up for the local demo.")
    )
    if not _can_mutate(role):
        return detail_panel("Generated email", [("Subject", subject), ("Body", body)])
    return html.Section(
        [
            html.H2("Generated email"),
            html.Div(
                [
                    dcc.Input(
                        id="sequence-activity-email-subject",
                        value=str(subject),
                        placeholder="Subject",
                        type="text",
                    ),
                    dcc.Textarea(
                        id="sequence-activity-email-body",
                        value=str(body),
                        placeholder="Email body",
                    ),
                ],
                className="form-grid compact-form",
            ),
        ],
        className="detail-panel",
    )


def _sequence_create_form(role: str) -> html.Div:
    if not _can_mutate(role):
        return html.Div()
    return html.Section(
        [
            html.H2("Create sequence"),
            html.Div(
                [
                    dcc.Input(id="sequence-create-name", placeholder="Name", type="text"),
                    dcc.Input(id="sequence-create-owner", placeholder="Owner", type="text"),
                    *_sequence_layer_inputs("sequence-create", []),
                    html.Button(
                        [icon("plus"), html.Span("Create sequence")],
                        id="sequence-create-submit",
                        n_clicks=0,
                        className="icon-button",
                    ),
                ],
                className="form-grid",
            ),
        ],
        className="detail-panel",
    )


def _crm_prospect_import_panel(
    prospects: list[dict[str, Any]],
    sequences: list[dict[str, Any]],
    role: str,
) -> html.Section:
    sequence_options = [
        {"label": sequence.get("name") or sequence.get("id"), "value": sequence.get("id")}
        for sequence in sequences
    ]
    default_sequence = sequence_options[0]["value"] if sequence_options else None
    controls = []
    if _can_mutate(role):
        controls = [
            dcc.Input(
                id="crm-prospect-query",
                placeholder="Search CRM prospects",
                type="text",
            ),
            dcc.Dropdown(
                id="crm-prospect-sequence",
                options=sequence_options,
                value=default_sequence,
                clearable=False,
            ),
            dcc.Textarea(
                id="crm-prospect-approval-reason",
                value="Approved for local demo outreach.",
            ),
        ]
    rows = [
        {
            **prospect,
            "company": prospect.get("company_name") or prospect.get("company_domain"),
        }
        for prospect in prospects
    ]
    return html.Section(
        [
            html.H2("CRM prospect import"),
            html.Div(controls, className="form-grid"),
            records_table(
                rows,
                [
                    ("Prospect", "display_name"),
                    ("Email", "email"),
                    ("Title", "title"),
                    ("Company", "company"),
                ],
                actions=lambda record: [
                    action_button(
                        "Assign",
                        {
                            "type": "crm-prospect-import",
                            "provider_record_id": record.get("provider_record_id"),
                        },
                        "user-plus",
                        disabled=not _can_mutate(role) or not default_sequence,
                    )
                ],
                empty_message="No CRM prospects returned.",
            ),
        ],
        className="detail-panel",
    )


def _review_edit_panel(record: dict[str, Any], role: str) -> html.Div:
    if not _can_mutate(role):
        return html.Div()
    return html.Section(
        [
            html.H2("Edit contact"),
            html.Div(
                [
                    dcc.Input(
                        id="review-edit-name",
                        value=record.get("name"),
                        placeholder="Name",
                        type="text",
                    ),
                    dcc.Input(
                        id="review-edit-company",
                        value=record.get("company"),
                        placeholder="Company",
                        type="text",
                    ),
                    dcc.Input(
                        id="review-edit-domain",
                        value=record.get("domain"),
                        placeholder="Domain",
                        type="text",
                    ),
                    dcc.Input(
                        id="review-edit-email",
                        value=record.get("email"),
                        placeholder="Email",
                        type="email",
                    ),
                    html.Button(
                        [icon("save"), html.Span("Save")],
                        id="review-edit-submit",
                        n_clicks=0,
                        className="icon-button",
                    ),
                ],
                className="form-grid compact-form",
            ),
        ],
        className="detail-panel",
    )


def _crm_target_edit_panel(record: dict[str, Any], role: str) -> html.Div:
    if not _can_mutate(role):
        return html.Div()
    return html.Section(
        [
            html.H2("Edit CRM contact"),
            html.Div(
                [
                    dcc.Input(
                        id="crm-target-edit-name",
                        value=record.get("name"),
                        placeholder="Name",
                        type="text",
                    ),
                    dcc.Input(
                        id="crm-target-edit-company",
                        value=record.get("company"),
                        placeholder="Company",
                        type="text",
                    ),
                    dcc.Input(
                        id="crm-target-edit-email",
                        value=record.get("email"),
                        placeholder="Email",
                        type="email",
                    ),
                    html.Button(
                        [icon("save"), html.Span("Save")],
                        id="crm-target-edit-submit",
                        n_clicks=0,
                        className="icon-button",
                    ),
                ],
                className="form-grid compact-form",
            ),
        ],
        className="detail-panel",
    )


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
                ("Version", sequence.get("definition_version")),
                ("Rate limits", sequence.get("rate_limit_policy")),
            ],
        )
    return html.Section(
        [
            html.H2("Edit sequence"),
            dcc.Store(id="sequence-edit-version", data=sequence.get("definition_version") or 1),
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
                    *_sequence_layer_inputs("sequence-edit", sequence.get("steps") or []),
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


def _sequence_layer_inputs(prefix: str, steps: list[dict[str, Any]]) -> list[Any]:
    defaults = steps or [
        {
            "channel": "email",
            "delay_seconds": 0,
            "subject_template": "Following up on {account_name}",
            "body_template": "Hi {contact_first_name}, checking in.",
            "requires_approval": True,
        },
        {
            "channel": "call",
            "delay_seconds": 86400,
            "step_metadata": {"instructions": "Call and log security priorities."},
            "requires_approval": False,
        },
        {
            "channel": "google_meet",
            "delay_seconds": 172800,
            "step_metadata": {"meeting_subject": "Security discovery"},
            "requires_approval": False,
        },
    ]
    layers: list[Any] = []
    for index in range(SEQUENCE_LAYER_COUNT):
        step = defaults[index] if index < len(defaults) else {}
        metadata = step.get("step_metadata") if isinstance(step.get("step_metadata"), dict) else {}
        has_step = bool(step)
        layers.append(
            html.Div(
                [
                    html.H3(f"Layer {index + 1}"),
                    dcc.Dropdown(
                        id=f"{prefix}-step-{index + 1}-channel",
                        value=step.get("channel") if has_step else None,
                        clearable=True,
                        options=[
                            {"label": "Email", "value": "email"},
                            {"label": "Call", "value": "call"},
                            {"label": "Google Meet", "value": "google_meet"},
                        ],
                    ),
                    dcc.Input(
                        id=f"{prefix}-step-{index + 1}-delay-days",
                        value=str(int(step.get("delay_seconds") or 0) // 86400) if has_step else "",
                        placeholder="Delay days",
                        type="number",
                    ),
                    dcc.Input(
                        id=f"{prefix}-step-{index + 1}-subject",
                        value=step.get("subject_template") or metadata.get("meeting_subject") or "",
                        placeholder="Subject",
                        type="text",
                    ),
                    dcc.Textarea(
                        id=f"{prefix}-step-{index + 1}-body",
                        value=step.get("body_template") or metadata.get("instructions") or "",
                        placeholder="Body or instructions",
                    ),
                    dcc.Checklist(
                        id=f"{prefix}-step-{index + 1}-approval",
                        options=[{"label": "Requires approval", "value": "yes"}],
                        value=["yes"] if step.get("requires_approval") else [],
                    ),
                ],
                className="sequence-layer",
            )
        )
    return layers


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


def _review_queue_row(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence = (
        candidate.get("evidence_summary")
        if isinstance(candidate.get("evidence_summary"), dict)
        else {}
    )
    payload = (
        evidence.get("candidate_payload")
        if isinstance(evidence.get("candidate_payload"), dict)
        else {}
    )
    return {
        **candidate,
        "name": evidence.get("published_name")
        or evidence.get("contact")
        or payload.get("published_name")
        or candidate.get("target_id"),
        "company": evidence.get("organization") or payload.get("company") or "-",
        "domain": evidence.get("domain") or payload.get("domain") or "-",
        "email": payload.get("verified_email") or evidence.get("email") or "-",
    }


def _crm_target_row(target: dict[str, Any]) -> dict[str, Any]:
    approval = (
        target.get("approval_snapshot") if isinstance(target.get("approval_snapshot"), dict) else {}
    )
    policy = (
        target.get("policy_snapshot") if isinstance(target.get("policy_snapshot"), dict) else {}
    )
    return {
        **target,
        "name": target.get("display_name")
        or approval.get("name")
        or policy.get("name")
        or target.get("target_id"),
        "company": target.get("company_name")
        or approval.get("company")
        or policy.get("company")
        or "-",
        "email": approval.get("email")
        or policy.get("email")
        or target.get("email")
        or (target.get("target_id") if target.get("target_type") == "email_candidate" else "-"),
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


def _prep_packet_panel(packet: Any) -> html.Section:
    if not isinstance(packet, dict) or not packet:
        return html.Section(
            [html.H2("Prep packet"), empty_state("No prep packet yet.")],
            className="detail-panel",
        )
    sections = [
        ("Account context", [packet.get("account_summary")]),
        ("Contacts", packet.get("stakeholder_map") or []),
        ("Signals", packet.get("likely_security_priorities") or []),
        ("Recommended talk tracks", packet.get("suggested_questions") or []),
        ("Risks and incidents", packet.get("risks") or []),
        ("Events and source context", _source_snapshot_rows(packet.get("source_snapshot"))),
    ]
    return html.Section(
        [
            html.H2("Prep packet"),
            html.Div(
                [
                    html.Div(
                        [
                            html.H3(title),
                            html.Div(
                                [_prep_packet_value(item) for item in _clean_items(items)],
                                className="prep-section-body",
                            ),
                        ],
                        className="prep-section",
                    )
                    for title, items in sections
                ],
                className="prep-packet",
            ),
        ],
        className="detail-panel prep-panel",
    )


def _clean_items(items: Any) -> list[Any]:
    if items in (None, "", []):
        return ["-"]
    if isinstance(items, list):
        return items or ["-"]
    return [items]


def _source_snapshot_rows(value: Any) -> list[Any]:
    if not isinstance(value, dict):
        return []
    return [
        {"label": human_label(key), "value": item}
        for key, item in value.items()
        if item not in (None, "", [], {})
    ]


def _prep_packet_value(value: Any) -> html.Div:
    if isinstance(value, dict):
        if "label" in value and "value" in value:
            return html.Div(
                [
                    html.Strong(str(value["label"])),
                    html.Span(render_inline_value(value["value"])),
                ],
                className="prep-row",
            )
        return html.Div(
            [
                html.Span(
                    f"{human_label(key)}: {render_inline_value(item)}",
                    className="prep-chip",
                )
                for key, item in value.items()
                if item not in (None, "", [], {})
            ],
            className="prep-row",
        )
    return html.Div(str(value), className="prep-row")


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


def _attendees_display(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "-"
    attendees: list[str] = []
    for item in value:
        if isinstance(item, dict):
            email = str(item.get("email") or "").strip()
            name = str(item.get("display_name") or item.get("name") or "").strip()
            if name and email:
                attendees.append(f"{name} <{email}>")
            elif email:
                attendees.append(email)
            elif name:
                attendees.append(name)
        elif item not in (None, ""):
            attendees.append(str(item))
    return ", ".join(attendees) if attendees else "-"


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
