from typing import Any

from dash import dcc, html
from dash.development.base_component import Component

from ghostrecon.console.components import (
    action_button,
    detail_panel,
    icon,
)

from .shared_values import _action_id, _can_mutate


def _sequence_actions(record: dict[str, Any], role: str) -> list[Any]:
    disabled = not _can_mutate(role)
    status = str(record.get("status") or "")
    terminal = status in {"completed", "canceled", "suppressed", "failed"}
    toggle_action = "resume" if status == "paused" else "pause"
    toggle_label = "Resume" if status == "paused" else "Pause"
    toggle_icon = "play" if status == "paused" else "pause"
    actions = [
        dcc.Link(
            "Open",
            href=f"/sequences/enrollments/{record.get('id')}",
            refresh=False,
            className="text-link",
        ),
        action_button(
            toggle_label,
            _action_id("sequence", toggle_action, record.get("id")),
            toggle_icon,
            disabled=disabled or terminal,
        ),
        action_button(
            "Cancel",
            _action_id("sequence", "cancel", record.get("id")),
            "x",
            disabled=disabled,
            danger=True,
        ),
    ]
    return actions


def _sequence_pause_modal() -> Component:
    return html.Div(
        [
            html.Div(
                [
                    html.H2("Pause sequence"),
                    html.Label("Reason", htmlFor="sequence-pause-reason"),
                    dcc.Textarea(
                        id="sequence-pause-reason",
                        placeholder="Why should this enrollment be paused?",
                    ),
                    html.Div(
                        [
                            html.Button(
                                [icon("check"), html.Span("Confirm")],
                                id="sequence-pause-confirm",
                                n_clicks=0,
                                className="icon-button",
                            ),
                            html.Button(
                                [icon("x"), html.Span("Cancel")],
                                id="sequence-pause-cancel",
                                n_clicks=0,
                                className="icon-button",
                            ),
                        ],
                        className="detail-actions",
                    ),
                ],
                className="modal-panel",
            )
        ],
        id="sequence-pause-modal",
        className="modal-backdrop hidden",
    )


def _sequence_activity_actions(record: dict[str, Any], role: str) -> list[Any]:
    disabled = not _can_mutate(role)
    channel = str(record.get("channel") or "")
    status = str(record.get("status") or "")
    actions = [
        dcc.Link(
            "Open",
            href=f"/sequences/activities/{record.get('id')}",
            refresh=False,
            className="text-link",
        )
    ]
    if channel == "email":
        actions.append(
            action_button(
                "Approve",
                _action_id("sequence-activity", "approve-email", record.get("id")),
                "send",
                disabled=disabled or status not in {"pending_approval", "approved"},
            )
        )
    if channel == "call":
        actions.append(
            action_button(
                "Complete",
                _action_id("sequence-activity", "complete", record.get("id")),
                "check",
                disabled=disabled or status != "pending",
            )
        )
    if channel == "google_meet":
        actions.append(
            action_button(
                "Schedule",
                _action_id("sequence-activity", "schedule-meeting", record.get("id")),
                "calendar-plus",
                disabled=disabled or status != "pending",
            )
        )
    return actions


def _sequence_activity_email_panel(activity: dict[str, Any], role: str) -> Component:
    metadata = activity.get("metadata") if isinstance(activity.get("metadata"), dict) else {}
    if activity.get("channel") != "email":
        return html.Div()
    subject = metadata.get("subject") or metadata.get("subject_template") or "Following up"
    body = (
        metadata.get("body")
        or metadata.get("body_template")
        or ("Hi, sharing a concise security follow-up for the local demo.")
    )
    if not _can_mutate(role):
        return detail_panel("Generated email", [("Subject", subject), ("Body", body)])
    return html.Section(
        [
            html.H2("Generated email"),
            html.Div(
                [
                    dcc.Input(
                        id="sequence-activity-email-subject",
                        value=str(subject),
                        placeholder="Subject",
                        type="text",
                    ),
                    dcc.Textarea(
                        id="sequence-activity-email-body",
                        value=str(body),
                        placeholder="Email body",
                    ),
                ],
                className="form-grid compact-form",
            ),
        ],
        className="detail-panel",
    )


def _sequence_alert_form(enrollment_id: str, role: str) -> Component:
    if not _can_mutate(role):
        return html.Div()
    return html.Section(
        [
            html.H2("Reminder alert"),
            html.Div(
                [
                    dcc.Input(
                        id={"type": "sequence-alert-recipient", "enrollment_id": enrollment_id},
                        placeholder="Recipient email",
                        type="email",
                    ),
                    dcc.Input(
                        id={"type": "sequence-alert-subject", "enrollment_id": enrollment_id},
                        placeholder="Subject",
                        type="text",
                    ),
                    dcc.Textarea(
                        id={"type": "sequence-alert-body", "enrollment_id": enrollment_id},
                        placeholder="Reminder body",
                    ),
                    html.Button(
                        [icon("bell"), html.Span("Create alert")],
                        id={"type": "sequence-alert-submit", "enrollment_id": enrollment_id},
                        n_clicks=0,
                        className="icon-button",
                    ),
                ],
                className="form-grid",
            ),
        ],
        className="detail-panel",
    )
