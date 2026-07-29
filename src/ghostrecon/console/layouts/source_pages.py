from typing import Any

from dash import html

from ghostrecon.console.api import (
    ConsoleApiClient,
)
from ghostrecon.console.components import (
    query_badges,
    records_table,
)

from .shared import _filtered, _page, _pagination, _safe_get


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
