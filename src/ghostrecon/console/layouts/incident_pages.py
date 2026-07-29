from typing import Any

from dash import html

from ghostrecon.console.api import (
    ConsoleApiClient,
)
from ghostrecon.console.components import (
    detail_panel,
    metadata_details,
    query_badges,
    records_table,
)
from ghostrecon.models.api import DashboardRole

from .incident_components import (
    _incident_actions,
    _incident_edit_modal,
    _incident_table_row,
    _manual_incident_form,
    _watch_actions,
)
from .shared import _filter_panel, _filtered, _page, _pagination, _safe_get
from .shared_values import _inline_list


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
