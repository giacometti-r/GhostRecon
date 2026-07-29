from typing import Any

from dash import dcc, html

from ghostrecon.common.config import Settings
from ghostrecon.console.api import (
    ConsoleApiClient,
    ConsoleApiError,
    dashboard_context_from_headers,
)
from ghostrecon.console.components import (
    empty_state,
    error_notice,
    icon,
    nav_link,
)
from ghostrecon.models.api import DashboardRole

from .constants import NAV_ITEMS
from .crm_pages import crm_export_detail_page, crm_exports_page, crm_target_detail_page
from .event_pages import event_detail_page, events_page
from .incident_pages import (
    incident_detail_page,
    incidents_page,
    watchlist_detail_page,
    watchlists_page,
)
from .meeting_pages import meeting_detail_page, meetings_page
from .overview import overview_page
from .review_pages import enrichment_review_page, review_detail_page, review_page
from .sequence_actions import _sequence_pause_modal
from .sequence_pages import (
    sequence_activity_detail_page,
    sequence_definition_detail_page,
    sequence_definitions_page,
    sequence_enrollment_detail_page,
    sequences_page,
)
from .shared import _page, _params
from .shared_values import _normalize_role
from .source_pages import source_health_page


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
