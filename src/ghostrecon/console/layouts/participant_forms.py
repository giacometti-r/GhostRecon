from dash import dcc, html
from dash.development.base_component import Component

from ghostrecon.console.components import (
    icon,
)

from .shared_values import _can_mutate


def _participant_enrich_form(event_id: str, role: str) -> Component:
    return html.Div()


def _event_participant_form(event_id: str, role: str) -> Component:
    if not _can_mutate(role):
        return html.Div()
    return html.Section(
        [
            html.H2("Add participant"),
            html.Div(
                [
                    dcc.Input(
                        id={"type": "event-participant-name", "event_id": event_id},
                        placeholder="Name",
                        type="text",
                    ),
                    dcc.Input(
                        id={"type": "event-participant-org", "event_id": event_id},
                        placeholder="Organization",
                        type="text",
                    ),
                    dcc.Input(
                        id={"type": "event-participant-role", "event_id": event_id},
                        placeholder="Role",
                        type="text",
                    ),
                    dcc.Dropdown(
                        id={"type": "event-participant-type", "event_id": event_id},
                        value="speaker",
                        clearable=False,
                        options=[
                            {"label": "Speaker", "value": "speaker"},
                            {"label": "Sponsor", "value": "sponsor"},
                            {"label": "Organizer", "value": "organizer"},
                            {"label": "Attendee", "value": "attendee"},
                        ],
                    ),
                    dcc.Input(
                        id={"type": "event-participant-profile", "event_id": event_id},
                        placeholder="Profile URL",
                        type="url",
                    ),
                    html.Button(
                        [icon("plus"), html.Span("Add participant")],
                        id={"type": "event-participant-submit", "event_id": event_id},
                        n_clicks=0,
                        className="icon-button",
                    ),
                ],
                className="form-grid compact-form",
            ),
        ],
        className="detail-panel",
    )
