from typing import Any

from dash import Input, Output, State, no_update

from ghostrecon.common.config import Settings
from ghostrecon.console.api import (
    ConsoleApiClient,
    ConsoleApiError,
    idempotency_key,
    normalize_role,
)
from ghostrecon.console.components import error_notice

from .common import MUTATING_ROLES
from .values import _clean, _path_tail, _success_notice


def register_review_callbacks(dash_app: Any, settings: Settings) -> None:
    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input("review-edit-submit", "n_clicks"),
        State("console-url", "pathname"),
        State("review-edit-name", "value"),
        State("review-edit-company", "value"),
        State("review-edit-domain", "value"),
        State("review-edit-email", "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def save_review_candidate_edit(
        clicks: int | None,
        pathname: str | None,
        name: str | None,
        company: str | None,
        domain: str | None,
        email: str | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any]:
        if (clicks or 0) < 1:
            return no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot edit review candidates"),
                no_update,
                False,
            )
        candidate_id = _path_tail(pathname, "/review/")
        if not candidate_id:
            return error_notice("Action failed", "missing review candidate id"), no_update, False
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        try:
            api.patch(
                f"/v1/review/candidates/{candidate_id}",
                payload={
                    "name": _clean(name),
                    "company": _clean(company),
                    "domain": _clean(domain),
                    "email": _clean(email),
                },
                idempotency_key=idempotency_key("review-edit", candidate_id),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False
        return _success_notice("Review candidate updated."), (token or 0) + 1, False

    @dash_app.callback(
        Output("mutation-status", "children", allow_duplicate=True),
        Output("mutation-refresh-token", "data", allow_duplicate=True),
        Output("mutation-status-clear", "disabled", allow_duplicate=True),
        Input("crm-target-edit-submit", "n_clicks"),
        State("console-url", "pathname"),
        State("crm-target-edit-name", "value"),
        State("crm-target-edit-company", "value"),
        State("crm-target-edit-email", "value"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def save_crm_target_edit(
        clicks: int | None,
        pathname: str | None,
        name: str | None,
        company: str | None,
        email: str | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any, Any]:
        if (clicks or 0) < 1:
            return no_update, no_update, no_update
        if normalize_role(role) not in MUTATING_ROLES:
            return (
                error_notice("Action failed", "viewer role cannot edit CRM targets"),
                no_update,
                False,
            )
        target_id = _path_tail(pathname, "/crm/exports/targets/")
        if not target_id:
            return error_notice("Action failed", "missing CRM target id"), no_update, False
        api = ConsoleApiClient.from_settings(
            settings, actor=actor or "dashboard", role=normalize_role(role)
        )
        try:
            api.patch(
                f"/v1/review/crm-targets/{target_id}",
                payload={"name": _clean(name), "company": _clean(company), "email": _clean(email)},
                idempotency_key=idempotency_key("crm-target-edit", target_id),
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update, False
        return _success_notice("CRM target updated."), (token or 0) + 1, False
