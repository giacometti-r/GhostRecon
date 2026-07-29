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
from .values import _clean, _csv, _datetime_value, _int, _success_notice


def register_incident_callbacks(dash_app: Any, settings: Settings) -> None:
    @dash_app.callback(
        Output("manual-incident-modal", "className"),
        Input("manual-incident-open", "n_clicks"),
        Input("manual-incident-cancel", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_manual_incident_modal(
        open_clicks: int | None, cancel_clicks: int | None
    ) -> str | NoUpdate:
        triggered = ctx.triggered_id
        if triggered == "manual-incident-open" and (open_clicks or 0) > 0:
            return "modal-backdrop"
        if triggered == "manual-incident-cancel" and (cancel_clicks or 0) > 0:
            return "modal-backdrop hidden"
        return no_update

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Output("manual-incident-modal", "className", allow_duplicate=True),
        Input("manual-incident-submit", "n_clicks"),
        State("manual-incident-title", "value"),
        State("manual-incident-company", "value"),
        State("manual-incident-type", "value"),
        State("manual-incident-first-observed", "value"),
        State("manual-incident-source-items", "value"),
        State("manual-incident-domains", "value"),
        State("manual-incident-vector", "value"),
        State("manual-incident-evidence-urls", "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def create_manual_incident(
        clicks: int | None,
        title: str | None,
        companies: str | None,
        incident_type: str | None,
        first_observed: str | None,
        source_items: str | None,
        domains: str | None,
        vector: str | None,
        evidence_urls: str | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any, Any]:
        if (clicks or 0) < 1:
            return no_update, no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot create incidents"),
                no_update,
                False,
                no_update,
            )
        if not (title or "").strip():
            return error_notice("Incident title required"), no_update, False, no_update
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        payload = {
            "title": title.strip(),
            "affected_companies": _csv(companies),
            "affected_domains": _csv(domains, none_values=True),
            "incident_type": _clean(incident_type),
            "attack_vector": _clean(vector),
            "first_observed_at": _datetime_value(first_observed),
            "source_item_ids": _csv(source_items),
            "evidence_urls": _csv(evidence_urls),
        }
        try:
            result = api.post(
                "/v1/intelligence/incidents/manual",
                payload=payload,
                idempotency_key=idempotency_key("manual-incident", title.strip()),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False, no_update
        count = len(result.get("incidents") or [])
        return (
            _success_notice(f"Manual incident {title.strip()} created ({count} row(s))."),
            (token or 0) + 1,
            False,
            "modal-backdrop hidden",
        )

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input({"type": "incident-edit-submit", "incident_id": ALL, "version": ALL}, "n_clicks"),
        State("incident-edit-title", "value"),
        State("incident-edit-company", "value"),
        State("incident-edit-domains", "value"),
        State("incident-edit-type", "value"),
        State("incident-edit-vector", "value"),
        State("incident-edit-first-observed", "value"),
        State("incident-edit-evidence-urls", "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def save_incident_edit(
        clicks: list[int] | None,
        title: str | None,
        companies: str | None,
        domains: str | None,
        incident_type: str | None,
        vector: str | None,
        first_observed: str | None,
        evidence_urls: str | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any]:
        action_id = ctx.triggered_id
        if not isinstance(action_id, dict) or not any(clicks or []):
            return no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot edit incidents"),
                no_update,
                False,
            )
        incident_id = str(action_id.get("incident_id") or "")
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        try:
            api.patch(
                f"/v1/intelligence/incidents/{incident_id}",
                payload={
                    "version": _int(action_id.get("version")),
                    "title": _clean(title),
                    "affected_companies": _csv(companies),
                    "affected_domains": _csv(domains, none_values=True),
                    "incident_type": _clean(incident_type),
                    "attack_vector": _clean(vector),
                    "first_observed_at": _datetime_value(first_observed),
                    "evidence_urls": _csv(evidence_urls),
                },
                idempotency_key=idempotency_key(
                    "incident-edit", incident_id, action_id.get("version")
                ),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False
        return _success_notice("Incident updated."), (token or 0) + 1, False
