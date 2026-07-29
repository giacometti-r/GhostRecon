from typing import Any

from dash import dcc, html

from ghostrecon.console.api import (
    ConsoleApiClient,
)
from ghostrecon.console.components import (
    action_button,
    detail_panel,
    icon,
    query_badges,
    records_table,
)

from .constants import REPORTING_LIMIT
from .sequence_actions import (
    _sequence_actions,
    _sequence_activity_actions,
    _sequence_activity_email_panel,
    _sequence_alert_form,
)
from .sequence_forms import _sequence_create_form, _sequence_edit_form
from .sequence_rows import (
    _sequence_activity_row,
    _sequence_enrollment_row,
    _sequence_row,
    _sequence_step_row,
)
from .shared import _filter_panel, _filtered, _page, _safe_get
from .shared_values import _action_id, _can_mutate


def sequences_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div:
    payload = _safe_get(client, "/v1/sequences/enrollments", _filtered(params, "status"))
    activities = _safe_get(client, "/v1/sequences/activities", {"limit": REPORTING_LIMIT})
    children = [
        query_badges(params),
        _filter_panel(
            "/sequences",
            params,
            [
                ("status", "Enrollment status"),
            ],
        ),
        html.Div(
            [
                dcc.Link(
                    [icon("list-plus"), html.Span("Sequence Definitions")],
                    href="/sequences/definitions",
                    refresh=False,
                    className="icon-button link-button",
                )
            ],
            className="detail-actions",
        ),
        html.Section(
            [
                html.H2("Sequence activities"),
                records_table(
                    [
                        _sequence_activity_row(activity)
                        for activity in activities.get("activities", [])
                    ],
                    [
                        ("Prospect", "contact_name"),
                        ("Company", "account_name"),
                        ("Channel", "channel"),
                        ("Status", "status"),
                        ("Due", "due_at"),
                        ("Step", "step_order"),
                    ],
                    actions=lambda record: _sequence_activity_actions(record, role),
                    empty_message="No pending sequence activities.",
                ),
            ],
            className="detail-panel",
        ),
        records_table(
            [
                _sequence_enrollment_row(enrollment)
                for enrollment in payload.get("enrollments", [])
                if params.get("status") or enrollment.get("status") not in {"canceled", "completed"}
            ],
            [
                ("Prospect", "contact_name"),
                ("Company", "account_name"),
                ("Email", "contact_email"),
                ("Sequence", "sequence_name"),
                ("Status", "status"),
                ("Current step", "current_step_order"),
                ("Next step", "next_step_at"),
                ("Pause reason", "pause_reason"),
            ],
            actions=lambda record: _sequence_actions(record, role),
        ),
        html.Div(
            "The console exposes pause, resume, cancel, and unsubscribe controls; it never "
            "offers a send-now bypass.",
            className="operator-note",
        ),
    ]
    return _page("Sequence State", [payload, activities], children)


def sequence_definitions_page(
    client: ConsoleApiClient, params: dict[str, Any], *, role: str
) -> html.Div:
    sequences = _safe_get(client, "/v1/sequences", {"limit": REPORTING_LIMIT})
    children = [
        query_badges(params),
        _sequence_create_form(role),
        records_table(
            [
                _sequence_row(sequence)
                for sequence in sequences.get("sequences", [])
                if sequence.get("status") != "archived"
            ],
            [
                ("Name", "name"),
                ("Owner", "owner_id"),
                ("Status", "status"),
                ("Version", "definition_version"),
                ("Channels", "channels"),
                ("Steps", "step_count"),
            ],
            actions=lambda record: [
                dcc.Link(
                    "Open",
                    href=f"/sequences/definitions/{record.get('id')}",
                    refresh=False,
                ),
                action_button(
                    "Delete",
                    _action_id("sequence-definition", "delete", record.get("id")),
                    "trash-2",
                    disabled=not _can_mutate(role),
                    danger=True,
                ),
            ],
        ),
    ]
    return _page("Sequence Definitions", [sequences], children)


def sequence_enrollment_detail_page(
    client: ConsoleApiClient, enrollment_id: str, *, role: str
) -> html.Div:
    enrollment = _safe_get(client, f"/v1/sequences/enrollments/{enrollment_id}")
    sequence_id = enrollment.get("sequence_id")
    sequence = (
        _safe_get(client, f"/v1/sequences/{sequence_id}")
        if sequence_id and "_error" not in enrollment
        else {}
    )
    children = [
        detail_panel(
            "Enrollment",
            [
                ("Prospect", enrollment.get("contact_name")),
                ("Email", enrollment.get("contact_email")),
                ("Company", enrollment.get("account_name") or enrollment.get("account_domain")),
                ("Sequence", enrollment.get("sequence_name") or enrollment.get("sequence_id")),
                ("CRM target", enrollment.get("crm_target_summary")),
                ("Status", enrollment.get("status")),
                ("Current step", enrollment.get("current_step_order")),
                ("Next step", enrollment.get("next_step_at")),
                ("Pause reason", enrollment.get("pause_reason")),
            ],
        ),
        html.Div(_sequence_actions(enrollment, role), className="detail-actions"),
        html.Section(
            [
                html.H2("Workflow"),
                records_table(
                    [_sequence_step_row(step) for step in sequence.get("steps", [])],
                    [
                        ("Step", "step_order"),
                        ("Wait", "delay_display"),
                        ("Subject", "subject_template"),
                        ("Channel", "channel"),
                        ("Approval", "requires_approval"),
                    ],
                ),
            ],
            className="detail-panel",
        ),
        records_table(
            enrollment.get("outbound_emails", []),
            [
                ("To", "to_email"),
                ("Subject", "subject"),
                ("Status", "status"),
                ("Scheduled", "scheduled_at"),
                ("Sent", "sent_at"),
            ],
        ),
        _sequence_alert_form(enrollment_id, role),
    ]
    return _page("Sequence Enrollment", [enrollment], children)


def sequence_activity_detail_page(
    client: ConsoleApiClient, activity_id: str, *, role: str
) -> html.Div:
    activity = _safe_get(client, f"/v1/sequences/activities/{activity_id}")
    metadata = activity.get("metadata") if isinstance(activity.get("metadata"), dict) else {}
    children = [
        detail_panel(
            "Sequence Activity",
            [
                ("Prospect", activity.get("contact_name")),
                ("Company", activity.get("account_name")),
                ("Email", activity.get("contact_email")),
                ("Sequence", activity.get("sequence_name")),
                ("Channel", activity.get("channel")),
                ("Status", activity.get("status")),
                ("Due", activity.get("due_at")),
            ],
        ),
        _sequence_activity_email_panel(activity, role),
        detail_panel("Activity metadata", [("Metadata", metadata)]),
        html.Div(_sequence_activity_actions(activity, role), className="detail-actions"),
    ]
    return _page("Sequence Activity", [activity], children)


def sequence_definition_detail_page(
    client: ConsoleApiClient, sequence_id: str, *, role: str
) -> html.Div:
    sequence = _safe_get(client, f"/v1/sequences/{sequence_id}")
    children = [
        _sequence_edit_form(sequence, role),
        records_table(
            [_sequence_step_row(step) for step in sequence.get("steps", [])],
            [
                ("Step", "step_order"),
                ("Channel", "channel"),
                ("Wait", "delay_display"),
                ("Subject", "subject_template"),
                ("Instructions", "instruction_summary"),
                ("Active", "active"),
            ],
        ),
    ]
    return _page("Sequence Definition", [sequence], children)
