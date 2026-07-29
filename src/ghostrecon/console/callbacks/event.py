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

from .common import MUTATING_ROLES
from .values import _clean, _csv, _datetime_value, _first_value, _int, _success_notice


def register_event_callbacks(dash_app: Any, settings: Settings) -> None:
    @dash_app.callback(
        Output("manual-event-modal", "className"),
        Input("manual-event-open", "n_clicks"),
        Input("manual-event-cancel", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_manual_event_modal(
        open_clicks: int | None, cancel_clicks: int | None
    ) -> str | NoUpdate:
        triggered = ctx.triggered_id
        if triggered == "manual-event-open" and (open_clicks or 0) > 0:
            return "modal-backdrop"
        if triggered == "manual-event-cancel" and (cancel_clicks or 0) > 0:
            return "modal-backdrop hidden"
        return no_update

    @dash_app.callback(
        Output("event-edit-modal", "className"),
        Input("event-edit-open", "n_clicks"),
        Input("event-edit-cancel", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_event_edit_modal(
        open_clicks: int | None, cancel_clicks: int | None
    ) -> str | NoUpdate:
        triggered = ctx.triggered_id
        if triggered == "event-edit-open" and (open_clicks or 0) > 0:
            return "modal-backdrop"
        if triggered == "event-edit-cancel" and (cancel_clicks or 0) > 0:
            return "modal-backdrop hidden"
        return no_update

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Output("manual-event-modal", "className", allow_duplicate=True),
        Input("manual-event-submit", "n_clicks"),
        State("manual-event-name", "value"),
        State("manual-event-url", "value"),
        State("manual-event-start", "value"),
        State("manual-event-format", "value"),
        State("manual-event-venue", "value"),
        State("manual-event-street", "value"),
        State("manual-event-city", "value"),
        State("manual-event-region", "value"),
        State("manual-event-postcode", "value"),
        State("manual-event-country", "value"),
        State("manual-event-virtual-url", "value"),
        State("manual-event-topics", "value"),
        State("manual-event-source-items", "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def create_manual_event(
        clicks: int | None,
        name: str | None,
        canonical_url: str | None,
        starts_at: str | None,
        event_format: str | None,
        venue: str | None,
        street: str | None,
        city: str | None,
        region: str | None,
        postcode: str | None,
        country: str | None,
        virtual_url: str | None,
        topics: str | None,
        source_items: str | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any, Any]:
        if (clicks or 0) < 1:
            return no_update, no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot create events"),
                no_update,
                False,
                no_update,
            )
        if not (name or "").strip():
            return error_notice("Event name required"), no_update, False, no_update
        if not (canonical_url or "").strip() or not (starts_at or "").strip():
            return error_notice("Event URL and UTC start are required"), no_update, False, no_update
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        payload = {
            "name": name.strip(),
            "canonical_url": canonical_url.strip(),
            "starts_at_utc": _datetime_value(starts_at),
            "event_format": event_format or "unknown",
            "venue_name": _clean(venue),
            "street_address": _clean(street),
            "city": _clean(city),
            "region": _clean(region),
            "postcode": _clean(postcode),
            "country": _clean(country),
            "virtual_url": _clean(virtual_url),
            "topics": _csv(topics),
            "source_item_ids": _csv(source_items),
        }
        try:
            api.post(
                "/v1/intelligence/events/manual",
                payload=payload,
                idempotency_key=idempotency_key(
                    "manual-event", name.strip(), canonical_url.strip()
                ),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False, no_update
        return (
            _success_notice(f"Manual event {name.strip()} created."),
            (token or 0) + 1,
            False,
            "modal-backdrop hidden",
        )

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Output("event-edit-modal", "className", allow_duplicate=True),
        Input({"type": "event-edit-submit", "event_id": ALL, "version": ALL}, "n_clicks"),
        State("event-edit-name", "value"),
        State("event-edit-url", "value"),
        State("event-edit-start", "value"),
        State("event-edit-format", "value"),
        State("event-edit-venue", "value"),
        State("event-edit-street", "value"),
        State("event-edit-city", "value"),
        State("event-edit-region", "value"),
        State("event-edit-postcode", "value"),
        State("event-edit-country", "value"),
        State("event-edit-virtual-url", "value"),
        State("event-edit-topics", "value"),
        State("event-edit-source-items", "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def save_event_edit(
        clicks: list[int] | None,
        name: str | None,
        canonical_url: str | None,
        starts_at: str | None,
        event_format: str | None,
        venue: str | None,
        street: str | None,
        city: str | None,
        region: str | None,
        postcode: str | None,
        country: str | None,
        virtual_url: str | None,
        topics: str | None,
        source_items: str | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any, Any]:
        action_id = ctx.triggered_id
        if not isinstance(action_id, dict) or not any(clicks or []):
            return no_update, no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot edit events"),
                no_update,
                False,
                no_update,
            )
        event_id = str(action_id.get("event_id") or "")
        if not event_id:
            return error_notice("Action failed", "missing event id"), no_update, False, no_update
        payload = {
            "version": _int(action_id.get("version")),
            "name": _clean(name),
            "canonical_url": _clean(canonical_url),
            "starts_at_utc": _datetime_value(starts_at),
            "event_format": event_format or "unknown",
            "venue_name": _clean(venue),
            "street_address": _clean(street),
            "city": _clean(city),
            "region": _clean(region),
            "postcode": _clean(postcode),
            "country": _clean(country),
            "virtual_url": _clean(virtual_url),
            "topics": _csv(topics),
            "source_item_ids": _csv(source_items),
        }
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        try:
            api.patch(
                f"/v1/intelligence/events/{event_id}",
                payload=payload,
                idempotency_key=idempotency_key("event-edit", event_id, payload["version"]),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False, no_update
        return _success_notice("Event updated."), (token or 0) + 1, False, "modal-backdrop hidden"

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input({"type": "event-participant-submit", "event_id": ALL}, "n_clicks"),
        State({"type": "event-participant-name", "event_id": ALL}, "value"),
        State({"type": "event-participant-org", "event_id": ALL}, "value"),
        State({"type": "event-participant-role", "event_id": ALL}, "value"),
        State({"type": "event-participant-type", "event_id": ALL}, "value"),
        State({"type": "event-participant-profile", "event_id": ALL}, "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def create_event_participant(
        clicks: list[int] | None,
        names: list[str] | None,
        orgs: list[str] | None,
        roles: list[str] | None,
        participant_types: list[str] | None,
        profile_urls: list[str] | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any]:
        action_id = ctx.triggered_id
        if not isinstance(action_id, dict) or not any(clicks or []):
            return no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot create participants"),
                no_update,
                False,
            )
        name = _first_value(names)
        if not name:
            return error_notice("Participant name required"), no_update, False
        event_id = str(action_id.get("event_id") or "")
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        payload = {
            "published_name": name,
            "organization": _first_value(orgs),
            "published_role": _first_value(roles),
            "participant_type": _first_value(participant_types) or "speaker",
            "profile_url": _first_value(profile_urls),
            "reuse_state": "allowed",
            "contact_extraction_allowed": True,
            "crm_export_allowed": False,
        }
        try:
            api.post(
                f"/v1/intelligence/events/{event_id}/participants",
                payload=payload,
                idempotency_key=idempotency_key("event-participant", event_id, name),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False
        return _success_notice(f"Participant {name} added."), (token or 0) + 1, False
