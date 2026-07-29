from typing import Any
from urllib.parse import parse_qs

from dash import dcc, html

from ghostrecon.console.api import (
    ConsoleApiClient,
    ConsoleApiError,
)
from ghostrecon.console.components import (
    error_notice,
    icon,
    metadata_banner,
    page_header,
)

from .constants import REPORTING_LIMIT


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
