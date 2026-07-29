from collections import Counter
from typing import Any

from dash import dcc, html
from dash.development.base_component import Component
from plotly import graph_objects as go

from ghostrecon.console.components import (
    empty_state,
)


def _event_calendar(events: list[dict[str, Any]]) -> Component:
    buckets = Counter(
        str(event.get("starts_at_utc") or event.get("original_start") or "unknown")[:10]
        for event in events
    )
    if not buckets:
        return empty_state("Calendar has no event dates for this filter.")
    figure = go.Figure(data=[go.Bar(x=list(buckets.keys()), y=list(buckets.values()))])
    figure.update_layout(margin={"l": 32, "r": 16, "t": 20, "b": 32}, height=240)
    return html.Section([html.H2("Calendar"), dcc.Graph(figure=figure)], className="chart-panel")


def _event_map(events: list[dict[str, Any]]) -> Component:
    points = [
        event
        for event in events
        if event.get("latitude") is not None and event.get("longitude") is not None
    ]
    if not points:
        return empty_state("Map view needs geocoded event addresses.")
    figure = go.Figure(
        data=[
            go.Scattergeo(
                lat=[point.get("latitude") for point in points],
                lon=[point.get("longitude") for point in points],
                text=[_event_hover_text(point) for point in points],
                mode="markers",
                marker={"size": 11, "color": "#0f766e", "line": {"width": 1, "color": "#ffffff"}},
                hovertemplate="%{text}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        height=460,
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        showlegend=False,
        geo={
            "projection_type": "natural earth",
            "showland": True,
            "landcolor": "#eef2f7",
            "countrycolor": "#cbd5e1",
            "showocean": True,
            "oceancolor": "#e0f2fe",
        },
    )
    return html.Section(
        [html.H2("Event map"), dcc.Graph(figure=figure)], className="chart-panel event-map-panel"
    )


def _address(event: dict[str, Any]) -> str:
    locality = " ".join(str(part) for part in (event.get("postcode"), event.get("city")) if part)
    parts = [
        event.get("street_address"),
        locality,
        event.get("region"),
        event.get("country"),
    ]
    return ", ".join(str(part) for part in parts if part) or "-"


def _event_hover_text(event: dict[str, Any]) -> str:
    rows = [str(event.get("name") or "Event")]
    address = _address(event)
    if address != "-":
        rows.append(address)
    display_name = event.get("geocode_display_name")
    if display_name:
        rows.append(str(display_name))
    return "<br>".join(rows)


def _location(event: dict[str, Any]) -> str:
    parts = [event.get("venue_name"), event.get("city"), event.get("region"), event.get("country")]
    return ", ".join(str(part) for part in parts if part)
