from typing import Any

from dash import html

from ghostrecon.console.api import (
    ConsoleApiClient,
)
from ghostrecon.console.components import (
    detail_panel,
    query_badges,
    records_table,
)

from .crm_components import (
    _crm_batch_actions,
    _crm_target_actions,
    _crm_target_edit_panel,
    _crm_target_row,
)
from .shared import _filter_panel, _filtered, _page, _pagination, _safe_get


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
