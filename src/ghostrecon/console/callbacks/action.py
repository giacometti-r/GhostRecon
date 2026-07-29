from typing import Any

from dash import ALL, Input, Output, State, ctx, no_update

from ghostrecon.common.config import Settings
from ghostrecon.console.api import (
    ConsoleApiError,
)
from ghostrecon.console.components import error_notice

from .actions import perform_dashboard_action
from .common import ACTION_PATTERN
from .values import _dismissed_incidents, _first_value, _success_notice, _triggered_click_count


def register_action_callbacks(dash_app: Any, settings: Settings) -> None:
    @dash_app.callback(
        Output("mutation-status", "children"),
        Output("mutation-refresh-token", "data"),
        Output("mutation-status-clear", "disabled"),
        Output("dismissed-incident-ids", "data"),
        Input(ACTION_PATTERN, "n_clicks"),
        Input("mutation-status-clear", "n_intervals"),
        State({"type": "event-enrich-domain", "event_id": ALL}, "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        State("dismissed-incident-ids", "data"),
        prevent_initial_call=True,
    )
    def run_action(
        _clicks: list[int] | None,
        _clear_ticks: int | None,
        event_domains: list[str] | None,
        actor: str | None,
        role: str | None,
        token: int | None,
        dismissed_incident_ids: list[str] | None,
    ) -> tuple[Any, Any, Any, Any]:
        if ctx.triggered_id == "mutation-status-clear":
            return "", no_update, True, no_update
        action_id = ctx.triggered_id
        if not isinstance(action_id, dict):
            return no_update, no_update, no_update, no_update
        if _triggered_click_count() < 1:
            return no_update, no_update, no_update, no_update
        try:
            message = perform_dashboard_action(
                action_id,
                actor=actor or "dashboard",
                role=role,
                settings=settings,
                extra_payload={"domain": _first_value(event_domains)},
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False, no_update
        return (
            _success_notice(message),
            (token or 0) + 1,
            False,
            _dismissed_incidents(action_id, dismissed_incident_ids),
        )
