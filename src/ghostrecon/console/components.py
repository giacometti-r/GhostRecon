from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from dash import dcc, html
from dash.development.base_component import Component
from dash_iconify import DashIconify

from ghostrecon.console.api import any_stale, degraded_dependencies, metadata_from

ColumnSpec = tuple[str, str]
ActionFactory = Callable[[dict[str, Any]], list[Component]]


def icon(name: str, *, size: int = 18) -> DashIconify:
    return DashIconify(icon=f"lucide:{name}", width=size, height=size)


def nav_link(label: str, href: str, icon_name: str) -> dcc.Link:
    return dcc.Link(
        [icon(icon_name, size=17), html.Span(label)],
        href=href,
        className="nav-link",
    )


def page_header(
    title: str,
    subtitle: str | None = None,
    actions: list[Any] | None = None,
) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H1(title),
                    html.P(subtitle or "", className="page-subtitle"),
                ],
                className="page-title",
            ),
            html.Div(actions or [], className="page-actions"),
        ],
        className="page-header",
    )


def metadata_banner(payloads: list[dict[str, Any] | None]) -> html.Div:
    degraded = degraded_dependencies(payloads)
    stale = any_stale(payloads)
    if not stale and not degraded:
        return html.Div("Fresh", className="freshness-banner ok")
    detail = "Stale reporting data"
    if degraded:
        detail += f"; degraded: {', '.join(degraded)}"
    return html.Div(detail, className="freshness-banner warning")


def metadata_details(payload: dict[str, Any] | None) -> html.Div:
    metadata = metadata_from(payload)
    if not metadata:
        return html.Div("No freshness metadata returned.", className="muted")
    watermarks = metadata.get("watermarks") or {}
    fields = [
        ("Generated", metadata.get("generated_at")),
        ("Projection", metadata.get("projection_version")),
        ("Stale", metadata.get("stale")),
        ("Watermarks", watermarks),
    ]
    return html.Dl(
        [
            html.Div([html.Dt(label), html.Dd(format_value(value))], className="meta-row")
            for label, value in fields
        ],
        className="metadata-list",
    )


def summary_tile(label: str, value: int | str, detail: str | None = None) -> html.Div:
    return html.Div(
        [
            html.Div(label, className="tile-label"),
            html.Div(str(value), className="tile-value"),
            html.Div(detail or "", className="tile-detail"),
        ],
        className="summary-tile",
    )


def status_badge(value: Any) -> html.Span:
    normalized = str(value or "unknown").replace("_", " ")
    return html.Span(normalized, className=f"status-badge {css_token(value)}")


def action_button(
    label: str,
    action_id: dict[str, Any] | str,
    icon_name: str,
    *,
    disabled: bool = False,
    danger: bool = False,
) -> html.Button:
    class_name = "icon-button danger" if danger else "icon-button"
    return html.Button(
        [icon(icon_name, size=16), html.Span(label)],
        id=action_id,
        n_clicks=0,
        disabled=disabled,
        className=class_name,
        title=label,
    )


def records_table(
    records: list[dict[str, Any]],
    columns: list[ColumnSpec],
    *,
    actions: ActionFactory | None = None,
    empty_message: str = "No records match the current view.",
) -> html.Div:
    if not records:
        return empty_state(empty_message)

    header_cells = [html.Th(label, scope="col") for label, _ in columns]
    if actions:
        header_cells.append(html.Th("Actions", scope="col"))

    rows = []
    for record in records:
        cells = [html.Td(format_value(record.get(key))) for _, key in columns]
        if actions:
            cells.append(html.Td(actions(record), className="table-actions"))
        rows.append(html.Tr(cells))

    return html.Div(
        html.Table([html.Thead(html.Tr(header_cells)), html.Tbody(rows)], className="data-table"),
        className="table-wrap",
    )


def empty_state(message: str) -> html.Div:
    return html.Div([icon("inbox"), html.Span(message)], className="empty-state")


def error_notice(message: str, detail: str | None = None) -> html.Div:
    return html.Div(
        [html.Strong(message), html.P(detail or "", className="error-detail")],
        className="error-notice",
        role="alert",
    )


def query_badges(params: dict[str, Any]) -> html.Div:
    badges = [
        html.Span(f"{key}: {value}", className="query-badge")
        for key, value in params.items()
        if value not in (None, "")
    ]
    if not badges:
        badges = [html.Span("No filters", className="query-badge muted-badge")]
    return html.Div(badges, className="query-badges")


def detail_panel(title: str, rows: list[tuple[str, Any]]) -> html.Section:
    return html.Section(
        [
            html.H2(title),
            html.Dl(
                [
                    html.Div([html.Dt(label), html.Dd(format_value(value))], className="detail-row")
                    for label, value in rows
                ],
                className="detail-list",
            ),
        ],
        className="detail-panel",
    )


def json_block(value: Any) -> html.Pre:
    return html.Pre(format_json(value), className="json-block")


def format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, dict | list):
        return format_json(value)
    return str(value)


def format_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def css_token(value: Any) -> str:
    token = str(value or "unknown").lower()
    return "".join(char if char.isalnum() else "-" for char in token)
