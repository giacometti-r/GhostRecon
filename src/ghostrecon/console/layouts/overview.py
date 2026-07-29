from typing import Any

from dash import html

from ghostrecon.console.api import (
    ConsoleApiClient,
)
from ghostrecon.console.components import (
    detail_panel,
    human_label,
    records_table,
    summary_tile,
)

from .shared import _count, _page, _safe_get


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
