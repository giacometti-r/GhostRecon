from collections import Counter
from typing import Any

from dash import dcc, html
from dash.development.base_component import Component
from plotly import graph_objects as go

from ghostrecon.console.components import (
    action_button,
    empty_state,
    icon,
)

from .shared_values import _action_id, _can_mutate, _datetime_local_value, _inline_list


def _manual_incident_form(role: str) -> Component:
    if not _can_mutate(role):
        return html.Div()
    return html.Div(
        [
            html.Div(
                html.Button(
                    [icon("plus"), html.Span("Add incident")],
                    id="manual-incident-open",
                    n_clicks=0,
                    className="icon-button",
                ),
                className="form-launcher",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H2("Add incident"),
                            html.Div(
                                [
                                    dcc.Input(
                                        id="manual-incident-title",
                                        placeholder="Incident title",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-company",
                                        placeholder="Companies, comma separated",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-type",
                                        placeholder="Incident type",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-first-observed",
                                        placeholder="First observed",
                                        type="datetime-local",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-source-items",
                                        placeholder="Source item IDs, comma separated",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-domains",
                                        placeholder="Domains, comma separated",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-vector",
                                        placeholder="Attack vector",
                                        type="text",
                                    ),
                                    dcc.Input(
                                        id="manual-incident-evidence-urls",
                                        placeholder="Evidence URLs, comma separated",
                                        type="text",
                                    ),
                                ],
                                className="form-grid",
                            ),
                            html.Div(
                                [
                                    html.Button(
                                        [icon("check"), html.Span("Create")],
                                        id="manual-incident-submit",
                                        n_clicks=0,
                                        className="icon-button",
                                    ),
                                    html.Button(
                                        [icon("x"), html.Span("Cancel")],
                                        id="manual-incident-cancel",
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
                id="manual-incident-modal",
                className="modal-backdrop hidden",
            ),
        ],
        className="toolbar-block",
    )


def _incident_edit_modal(incident: dict[str, Any], role: str) -> Component:
    if not _can_mutate(role) or not incident.get("id"):
        return html.Div()
    return html.Section(
        [
            html.H2("Edit incident"),
            html.Div(
                [
                    dcc.Input(
                        id="incident-edit-title",
                        value=incident.get("title"),
                        placeholder="Title",
                        type="text",
                    ),
                    dcc.Input(
                        id="incident-edit-company",
                        value=_inline_list(incident.get("affected_companies")),
                        placeholder="Companies",
                        type="text",
                    ),
                    dcc.Input(
                        id="incident-edit-domains",
                        value=_inline_list(incident.get("affected_domains")),
                        placeholder="Domains",
                        type="text",
                    ),
                    dcc.Input(
                        id="incident-edit-type",
                        value=incident.get("incident_type"),
                        placeholder="Type",
                        type="text",
                    ),
                    dcc.Input(
                        id="incident-edit-vector",
                        value=incident.get("attack_vector"),
                        placeholder="Attack vector",
                        type="text",
                    ),
                    dcc.Input(
                        id="incident-edit-first-observed",
                        value=_datetime_local_value(incident.get("first_observed_at")),
                        placeholder="First observed",
                        type="datetime-local",
                    ),
                    dcc.Input(
                        id="incident-edit-evidence-urls",
                        value=_inline_list(incident.get("evidence_urls")),
                        placeholder="Evidence URLs",
                        type="text",
                    ),
                    html.Button(
                        [icon("save"), html.Span("Save incident")],
                        id={
                            "type": "incident-edit-submit",
                            "incident_id": str(incident.get("id") or ""),
                            "version": incident.get("version"),
                        },
                        n_clicks=0,
                        className="icon-button",
                    ),
                ],
                className="form-grid compact-form",
            ),
        ],
        className="detail-panel",
    )


def _incident_chart(incidents: list[dict[str, Any]]) -> Component:
    buckets = Counter(str(incident.get("status") or "unknown") for incident in incidents)
    if not buckets:
        return empty_state("No incident status data for this filter.")
    figure = go.Figure(data=[go.Bar(x=list(buckets.keys()), y=list(buckets.values()))])
    figure.update_layout(margin={"l": 32, "r": 16, "t": 20, "b": 32}, height=220)
    return html.Section(
        [html.H2("Incident Status"), dcc.Graph(figure=figure)],
        className="chart-panel",
    )


def _incident_actions(record: dict[str, Any], role: str, *, include_open: bool = True) -> list[Any]:
    disabled = not _can_mutate(role)
    version_missing = record.get("version") is None
    status = str(record.get("status") or "")
    actions: list[Any] = []
    if include_open:
        actions.append(
            dcc.Link(
                "Open",
                href=f"/incidents/{record.get('id')}",
                refresh=False,
                className="text-link",
            )
        )
    actions.extend(
        [
            action_button(
                "Add to Watchlist",
                _action_id(
                    "incident",
                    "promote",
                    record.get("id"),
                    record.get("version"),
                    enabled=status,
                ),
                "radar",
                disabled=disabled or version_missing,
            ),
            action_button(
                "Reject",
                _action_id("incident", "reject", record.get("id"), record.get("version")),
                "x",
                disabled=disabled or version_missing,
                danger=True,
            ),
        ]
    )
    return actions


def _watch_actions(record: dict[str, Any], role: str, *, include_open: bool = True) -> list[Any]:
    next_enabled = not bool(record.get("enabled"))
    actions: list[Any] = []
    if include_open:
        actions.append(
            dcc.Link(
                "Open",
                href=f"/watchlists/{record.get('id')}",
                refresh=False,
                className="text-link",
            )
        )
    actions.extend(
        [
            action_button(
                "Find Contact",
                _action_id("watch", "find-contact", record.get("id")),
                "search",
                disabled=not _can_mutate(role),
            ),
            action_button(
                "Enable Monitoring" if next_enabled else "Pause Monitoring",
                _action_id(
                    "watch",
                    "toggle",
                    record.get("id"),
                    record.get("version"),
                    enabled=next_enabled,
                ),
                "play" if next_enabled else "pause",
                disabled=not _can_mutate(role),
            ),
        ]
    )
    return actions


def _incident_table_row(incident: dict[str, Any]) -> dict[str, Any]:
    companies = incident.get("affected_companies") or [incident.get("primary_affected_company")]
    evidence = [
        *(incident.get("evidence_families") or []),
        *(incident.get("evidence_urls") or []),
    ]
    return {
        **incident,
        "company_display": _inline_list(companies),
        "evidence_display": _inline_list(evidence),
    }
