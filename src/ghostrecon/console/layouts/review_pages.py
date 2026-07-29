from typing import Any

from dash import dcc, html

from ghostrecon.console.api import (
    ConsoleApiClient,
)
from ghostrecon.console.components import (
    detail_panel,
    query_badges,
    records_table,
)

from .review_components import (
    _bulk_contact_queue_actions,
    _bulk_review_actions,
    _contact_queue_actions,
    _contact_queue_row,
    _review_actions,
    _review_edit_panel,
    _review_queue_row,
)
from .shared import _filter_panel, _filtered, _page, _pagination, _safe_get


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
