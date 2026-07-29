from typing import Any

from dash import Input, Output, html

from ghostrecon.common.config import Settings
from ghostrecon.console.layouts import render_navigation, render_page


def register_navigation_callbacks(dash_app: Any, settings: Settings) -> None:
    @dash_app.callback(
        Output("page-content", "children"),
        Input("console-url", "pathname"),
        Input("console-url", "search"),
        Input("operator-actor", "value"),
        Input("operator-role", "value"),
        Input("refresh-page", "n_clicks"),
        Input("mutation-refresh-token", "data"),
        Input("dismissed-incident-ids", "data"),
    )
    def route_page(
        pathname: str | None,
        search: str | None,
        actor: str | None,
        role: str | None,
        _refresh_clicks: int | None,
        _mutation_refresh: int | None,
        dismissed_incident_ids: list[str] | None,
    ) -> html.Div:
        return render_page(
            pathname,
            search,
            actor,
            role,
            settings,
            dismissed_incident_ids=dismissed_incident_ids,
        )

    @dash_app.callback(
        Output("sidebar-nav", "children"),
        Input("console-url", "pathname"),
    )
    def route_navigation(pathname: str | None) -> list[Any]:
        return render_navigation(pathname)
