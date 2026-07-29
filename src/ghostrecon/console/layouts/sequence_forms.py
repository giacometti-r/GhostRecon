from typing import Any

from dash import dcc, html
from dash.development.base_component import Component

from ghostrecon.console.components import (
    detail_panel,
    icon,
)

from .constants import SEQUENCE_LAYER_COUNT
from .shared_values import _can_mutate


def _sequence_create_form(role: str) -> Component:
    if not _can_mutate(role):
        return html.Div()
    return html.Section(
        [
            html.H2("Create sequence"),
            html.Div(
                [
                    dcc.Input(id="sequence-create-name", placeholder="Name", type="text"),
                    dcc.Input(id="sequence-create-owner", placeholder="Owner", type="text"),
                    *_sequence_layer_inputs("sequence-create", []),
                    html.Button(
                        [icon("plus"), html.Span("Create sequence")],
                        id="sequence-create-submit",
                        n_clicks=0,
                        className="icon-button",
                    ),
                ],
                className="form-grid",
            ),
        ],
        className="detail-panel",
    )


def _sequence_edit_form(sequence: dict[str, Any], role: str) -> Component:
    if not _can_mutate(role):
        return detail_panel(
            "Sequence",
            [
                ("Name", sequence.get("name")),
                ("Owner", sequence.get("owner_id")),
                ("Status", sequence.get("status")),
                ("Version", sequence.get("definition_version")),
                ("Rate limits", sequence.get("rate_limit_policy")),
            ],
        )
    return html.Section(
        [
            html.H2("Edit sequence"),
            dcc.Store(id="sequence-edit-version", data=sequence.get("definition_version") or 1),
            html.Div(
                [
                    dcc.Input(
                        id="sequence-edit-name",
                        value=sequence.get("name"),
                        placeholder="Name",
                        type="text",
                    ),
                    dcc.Input(
                        id="sequence-edit-owner",
                        value=sequence.get("owner_id"),
                        placeholder="Owner",
                        type="text",
                    ),
                    dcc.Dropdown(
                        id="sequence-edit-status",
                        value=sequence.get("status"),
                        options=[
                            {"label": "Active", "value": "active"},
                            {"label": "Paused", "value": "paused"},
                            {"label": "Archived", "value": "archived"},
                        ],
                        clearable=False,
                    ),
                    *_sequence_layer_inputs("sequence-edit", sequence.get("steps") or []),
                    html.Button(
                        [icon("save"), html.Span("Save sequence")],
                        id={
                            "type": "sequence-edit-submit",
                            "sequence_id": str(sequence.get("id") or ""),
                        },
                        n_clicks=0,
                        className="icon-button",
                    ),
                ],
                className="form-grid",
            ),
        ],
        className="detail-panel",
    )


def _sequence_layer_inputs(prefix: str, steps: list[dict[str, Any]]) -> list[Any]:
    defaults = steps or [
        {
            "channel": "email",
            "delay_seconds": 0,
            "subject_template": "Following up on {account_name}",
            "body_template": "Hi {contact_first_name}, checking in.",
            "requires_approval": True,
        },
        {
            "channel": "call",
            "delay_seconds": 86400,
            "step_metadata": {"instructions": "Call and log security priorities."},
            "requires_approval": False,
        },
        {
            "channel": "google_meet",
            "delay_seconds": 172800,
            "step_metadata": {"meeting_subject": "Security discovery"},
            "requires_approval": False,
        },
    ]
    layers: list[Any] = []
    for index in range(SEQUENCE_LAYER_COUNT):
        step = defaults[index] if index < len(defaults) else {}
        metadata = step.get("step_metadata") if isinstance(step.get("step_metadata"), dict) else {}
        has_step = bool(step)
        layers.append(
            html.Div(
                [
                    html.H3(f"Layer {index + 1}"),
                    dcc.Dropdown(
                        id=f"{prefix}-step-{index + 1}-channel",
                        value=step.get("channel") if has_step else None,
                        clearable=True,
                        options=[
                            {"label": "Email", "value": "email"},
                            {"label": "Call", "value": "call"},
                            {"label": "Google Meet", "value": "google_meet"},
                        ],
                    ),
                    dcc.Input(
                        id=f"{prefix}-step-{index + 1}-delay-days",
                        value=str(int(step.get("delay_seconds") or 0) // 86400) if has_step else "",
                        placeholder="Delay days",
                        type="number",
                    ),
                    dcc.Input(
                        id=f"{prefix}-step-{index + 1}-subject",
                        value=step.get("subject_template") or metadata.get("meeting_subject") or "",
                        placeholder="Subject",
                        type="text",
                    ),
                    dcc.Textarea(
                        id=f"{prefix}-step-{index + 1}-body",
                        value=step.get("body_template") or metadata.get("instructions") or "",
                        placeholder="Body or instructions",
                    ),
                    dcc.Checklist(
                        id=f"{prefix}-step-{index + 1}-approval",
                        options=[{"label": "Requires approval", "value": "yes"}],
                        value=["yes"] if step.get("requires_approval") else [],
                    ),
                ],
                className="sequence-layer",
            )
        )
    return layers
