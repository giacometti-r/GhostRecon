from typing import Any

from dash import dcc, html
from dash.development.base_component import Component

from ghostrecon.console.components import (
    action_button,
    icon,
    records_table,
)

from .shared_values import _action_id, _can_mutate


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


def _crm_target_edit_panel(record: dict[str, Any], role: str) -> Component:
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
