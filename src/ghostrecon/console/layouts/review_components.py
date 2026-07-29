from typing import Any

from dash import dcc, html
from dash.development.base_component import Component

from ghostrecon.console.components import (
    action_button,
    icon,
)

from .shared_values import _action_id, _can_mutate, _provenance_label


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


def _review_edit_panel(record: dict[str, Any], role: str) -> Component:
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
