from typing import Any

from dash import dcc, html

from ghostrecon.console.components import (
    icon,
)

from .shared_values import _can_mutate, _datetime_local_value


def _manual_event_form(role: str) -> html.Div:
    if not _can_mutate(role):
        return html.Div()
    return html.Div(
        [
            html.Div(
                html.Button(
                    [icon("plus"), html.Span("Add event")],
                    id="manual-event-open",
                    n_clicks=0,
                    className="icon-button",
                ),
                className="form-launcher",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H2("Add event"),
                            html.Div(
                                [
                                    dcc.Input(
                                        id="manual-event-name",
                                        placeholder="Event name",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-url",
                                        placeholder="Canonical URL",
                                        type="url",
                                    ),
                                    dcc.Input(
                                        id="manual-event-start",
                                        placeholder="UTC start",
                                        type="datetime-local",
                                    ),
                                    dcc.Dropdown(
                                        id="manual-event-format",
                                        value="in-person",
                                        clearable=False,
                                        searchable=False,
                                        options=[
                                            {"label": "In person", "value": "in-person"},
                                            {"label": "Online", "value": "online"},
                                            {"label": "Hybrid", "value": "hybrid"},
                                            {"label": "Unknown", "value": "unknown"},
                                        ],
                                    ),
                                    dcc.Input(
                                        id="manual-event-venue",
                                        placeholder="Venue",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-street",
                                        placeholder="Street address",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-city",
                                        placeholder="City",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-region",
                                        placeholder="Region",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-postcode",
                                        placeholder="Postcode",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-country",
                                        placeholder="Country",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-virtual-url",
                                        placeholder="Meeting URL",
                                        type="url",
                                    ),
                                    dcc.Input(
                                        id="manual-event-topics",
                                        placeholder="Topics, comma separated",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-event-source-items",
                                        placeholder="Source item IDs, comma separated",
                                        type="text",
                                    ),
                                ],
                                className="form-grid",
                            ),
                            html.Div(
                                [
                                    html.Button(
                                        [icon("check"), html.Span("Create")],
                                        id="manual-event-submit",
                                        n_clicks=0,
                                        className="icon-button",
                                    ),
                                    html.Button(
                                        [icon("x"), html.Span("Cancel")],
                                        id="manual-event-cancel",
                                        n_clicks=0,
                                        className="icon-button",
                                    ),
                                ],
                                className="modal-actions",
                            ),
                        ],
                        className="modal-panel wide",
                    )
                ],
                id="manual-event-modal",
                className="modal-backdrop hidden",
            ),
        ],
        className="toolbar-block",
    )


def _event_edit_modal(event: dict[str, Any], role: str) -> html.Div:
    if not _can_mutate(role) or not event.get("id"):
        return html.Div()
    return html.Div(
        [
            html.Div(
                html.Button(
                    [icon("edit-3"), html.Span("Edit event")],
                    id="event-edit-open",
                    n_clicks=0,
                    className="icon-button",
                ),
                className="form-launcher",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H2("Edit event"),
                            html.Div(
                                [
                                    dcc.Input(
                                        id="event-edit-name",
                                        value=event.get("name"),
                                        placeholder="Event name",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-url",
                                        value=event.get("canonical_url"),
                                        placeholder="Canonical URL",
                                        type="url",
                                    ),
                                    dcc.Input(
                                        id="event-edit-start",
                                        value=_datetime_local_value(event.get("starts_at_utc")),
                                        placeholder="UTC start",
                                        type="datetime-local",
                                    ),
                                    dcc.Dropdown(
                                        id="event-edit-format",
                                        value=event.get("event_format") or "unknown",
                                        clearable=False,
                                        searchable=False,
                                        options=[
                                            {"label": "In person", "value": "in-person"},
                                            {"label": "Online", "value": "online"},
                                            {"label": "Hybrid", "value": "hybrid"},
                                            {"label": "Unknown", "value": "unknown"},
                                        ],
                                    ),
                                    dcc.Input(
                                        id="event-edit-venue",
                                        value=event.get("venue_name"),
                                        placeholder="Venue",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-street",
                                        value=event.get("street_address"),
                                        placeholder="Street address",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-city",
                                        value=event.get("city"),
                                        placeholder="City",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-region",
                                        value=event.get("region"),
                                        placeholder="Region",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-postcode",
                                        value=event.get("postcode"),
                                        placeholder="Postcode",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-country",
                                        value=event.get("country"),
                                        placeholder="Country",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-virtual-url",
                                        value=event.get("virtual_url"),
                                        placeholder="Meeting URL",
                                        type="url",
                                    ),
                                    dcc.Input(
                                        id="event-edit-topics",
                                        value=", ".join(
                                            str(item) for item in event.get("topics") or []
                                        ),
                                        placeholder="Topics, comma separated",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="event-edit-source-items",
                                        value=", ".join(
                                            str(item) for item in event.get("source_item_ids") or []
                                        ),
                                        placeholder="Source item IDs, comma separated",
                                        type="text",
                                    ),
                                ],
                                className="form-grid",
                            ),
                            html.Div(
                                [
                                    html.Button(
                                        [icon("save"), html.Span("Save")],
                                        id={
                                            "type": "event-edit-submit",
                                            "event_id": str(event.get("id") or ""),
                                            "version": event.get("version"),
                                        },
                                        n_clicks=0,
                                        className="icon-button",
                                    ),
                                    html.Button(
                                        [icon("x"), html.Span("Cancel")],
                                        id="event-edit-cancel",
                                        n_clicks=0,
                                        className="icon-button",
                                    ),
                                ],
                                className="modal-actions",
                            ),
                        ],
                        className="modal-panel wide",
                    )
                ],
                id="event-edit-modal",
                className="modal-backdrop hidden",
            ),
        ],
        className="toolbar-block",
    )
