from typing import Any

from dash import ALL, Input, Output, State, ctx, no_update
from dash._callback import NoUpdate

from ghostrecon.common.config import Settings
from ghostrecon.console.api import (
    ConsoleApiClient,
    ConsoleApiError,
    idempotency_key,
    normalize_role,
)
from ghostrecon.console.components import error_notice

from .actions import perform_dashboard_action
from .common import ACTION_PATTERN, MUTATING_ROLES, SEQUENCE_LAYER_COUNT
from .sequence_values import _sequence_layer_states, _sequence_steps_from_layers
from .values import _first_value, _success_notice


def register_sequence_callbacks(dash_app: Any, settings: Settings) -> None:
    @dash_app.callback(
        Output("sequence-pause-target", "data"),
        Output("sequence-pause-modal", "className"),
        Output("sequence-pause-reason", "value"),
        Input(ACTION_PATTERN, "n_clicks"),
        prevent_initial_call=True,
    )
    def open_sequence_pause_modal(
        _clicks: list[int] | None,
    ) -> tuple[NoUpdate, str | NoUpdate, str | NoUpdate]:
        return no_update, no_update, no_update

    @dash_app.callback(
        Output("sequence-pause-modal", "className", allow_duplicate=True),
        Output("sequence-pause-target", "data", allow_duplicate=True),
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input("sequence-pause-confirm", "n_clicks"),
        Input("sequence-pause-cancel", "n_clicks"),
        State("sequence-pause-target", "data"),
        State("sequence-pause-reason", "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def confirm_sequence_pause(
        confirm_clicks: int | None,
        cancel_clicks: int | None,
        action_id: dict[str, Any] | None,
        reason: str | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any, Any, Any]:
        triggered = ctx.triggered_id
        if triggered == "sequence-pause-cancel" and (cancel_clicks or 0) > 0:
            return "modal-backdrop hidden", {}, no_update, no_update, no_update
        if triggered != "sequence-pause-confirm" or (confirm_clicks or 0) < 1:
            return no_update, no_update, no_update, no_update, no_update
        if not action_id:
            return (
                "modal-backdrop hidden",
                {},
                error_notice("Action failed", "Missing sequence."),
                no_update,
                False,
            )
        if not (reason or "").strip():
            return (
                no_update,
                no_update,
                error_notice("Pause reason required", "Type a reason before confirming."),
                no_update,
                False,
            )
        try:
            message = perform_dashboard_action(
                action_id,
                actor=actor or "dashboard",
                role=role,
                settings=settings,
                extra_payload={"reason": reason.strip()},
            )
        except ConsoleApiError as exc:
            return no_update, no_update, error_notice("Action failed", str(exc)), no_update, False
        return "modal-backdrop hidden", {}, _success_notice(message), (token or 0) + 1, False

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input({"type": "sequence-alert-submit", "enrollment_id": ALL}, "n_clicks"),
        State({"type": "sequence-alert-recipient", "enrollment_id": ALL}, "value"),
        State({"type": "sequence-alert-subject", "enrollment_id": ALL}, "value"),
        State({"type": "sequence-alert-body", "enrollment_id": ALL}, "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def create_sequence_alert(
        clicks: list[int] | None,
        recipients: list[str] | None,
        subjects: list[str] | None,
        bodies: list[str] | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any]:
        action_id = ctx.triggered_id
        if not isinstance(action_id, dict) or not any(clicks or []):
            return no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot create alerts"),
                no_update,
                False,
            )
        recipient = _first_value(recipients)
        subject = _first_value(subjects)
        body = _first_value(bodies)
        if not recipient or not subject or not body:
            return error_notice("Alert fields required"), no_update, False
        enrollment_id = str(action_id.get("enrollment_id") or "")
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        try:
            api.post(
                f"/v1/sequences/enrollments/{enrollment_id}/alerts",
                payload={"recipient_email": recipient, "subject": subject, "body": body},
                idempotency_key=idempotency_key("sequence-alert", enrollment_id),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False
        return _success_notice("Reminder alert created."), (token or 0) + 1, False

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input("sequence-create-submit", "n_clicks"),
        State("sequence-create-name", "value"),
        State("sequence-create-owner", "value"),
        *_sequence_layer_states("sequence-create"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def create_sequence_definition(
        clicks: int | None,
        name: str | None,
        owner: str | None,
        *values: Any,
    ) -> tuple[Any, Any, Any]:
        layer_value_count = SEQUENCE_LAYER_COUNT * 5
        layer_values = list(values[:layer_value_count])
        actor = values[layer_value_count] if len(values) > layer_value_count else None
        role = values[layer_value_count + 1] if len(values) > layer_value_count + 1 else None
        token = values[layer_value_count + 2] if len(values) > layer_value_count + 2 else None
        if (clicks or 0) < 1:
            return no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot create sequences"),
                no_update,
                False,
            )
        steps = _sequence_steps_from_layers(layer_values)
        if not name or not steps:
            return error_notice("Sequence name and steps are required"), no_update, False
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        try:
            api.post(
                "/v1/sequences",
                payload={
                    "name": name.strip(),
                    "owner_id": (owner or "").strip() or (actor or "dashboard"),
                    "steps": steps,
                },
                idempotency_key=idempotency_key("sequence-create", name.strip()),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False
        return _success_notice("Sequence definition created."), (token or 0) + 1, False

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input({"type": "removed-crm-prospect-import", "provider_record_id": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def import_crm_prospect(_clicks: list[int] | None) -> tuple[Any, Any, Any]:
        return no_update, no_update, no_update

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input({"type": "sequence-edit-submit", "sequence_id": ALL}, "n_clicks"),
        State("sequence-edit-name", "value"),
        State("sequence-edit-owner", "value"),
        State("sequence-edit-status", "value"),
        *_sequence_layer_states("sequence-edit"),
        State("sequence-edit-version", "data"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def save_sequence_definition(
        clicks: list[int] | None,
        name: str | None,
        owner: str | None,
        status: str | None,
        *values: Any,
    ) -> tuple[Any, Any, Any]:
        layer_value_count = SEQUENCE_LAYER_COUNT * 5
        layer_values = list(values[:layer_value_count])
        version = values[layer_value_count] if len(values) > layer_value_count else None
        actor = values[layer_value_count + 1] if len(values) > layer_value_count + 1 else None
        role = values[layer_value_count + 2] if len(values) > layer_value_count + 2 else None
        token = values[layer_value_count + 3] if len(values) > layer_value_count + 3 else None
        action_id = ctx.triggered_id
        if not isinstance(action_id, dict) or not any(clicks or []):
            return no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot edit sequences"),
                no_update,
                False,
            )
        steps = _sequence_steps_from_layers(layer_values)
        sequence_id = str(action_id.get("sequence_id") or "")
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        try:
            api.patch(
                f"/v1/sequences/{sequence_id}",
                payload={
                    "name": (name or "").strip() or None,
                    "owner_id": (owner or "").strip() or None,
                    "status": status,
                    "steps": steps,
                    "expected_version": version,
                },
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False
        return _success_notice("Sequence definition updated."), (token or 0) + 1, False
