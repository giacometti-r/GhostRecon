from __future__ import annotations

from typing import Any

import httpx
from dash import ALL, Input, Output, State, ctx, html, no_update

from ghostrecon.common.config import Settings
from ghostrecon.console.api import (
    ConsoleApiClient,
    ConsoleApiError,
    idempotency_key,
    normalize_role,
)
from ghostrecon.console.components import error_notice, icon
from ghostrecon.console.layouts import render_page
from ghostrecon.models.api import DashboardRole

ACTION_PATTERN = {
    "type": "dashboard-action",
    "kind": ALL,
    "action": ALL,
    "target_id": ALL,
    "version": ALL,
    "policy_hash": ALL,
    "enabled": ALL,
}

MUTATING_ROLES = {
    DashboardRole.ANALYST.value,
    DashboardRole.GOVERNANCE_REVIEWER.value,
    DashboardRole.ADMINISTRATOR.value,
}


def register_callbacks(dash_app: Any, settings: Settings) -> None:
    @dash_app.callback(
        Output("page-content", "children"),
        Input("console-url", "pathname"),
        Input("console-url", "search"),
        Input("operator-actor", "value"),
        Input("operator-role", "value"),
        Input("refresh-page", "n_clicks"),
        Input("mutation-refresh-token", "data"),
    )
    def route_page(
        pathname: str | None,
        search: str | None,
        actor: str | None,
        role: str | None,
        _refresh_clicks: int | None,
        _mutation_refresh: int | None,
    ) -> html.Div:
        return render_page(pathname, search, actor, role, settings)

    @dash_app.callback(
        Output("mutation-status", "children"),
        Output("mutation-refresh-token", "data"),
        Input(ACTION_PATTERN, "n_clicks"),
        State("operator-actor", "value"),
        State("operator-role", "value"),
        State("mutation-refresh-token", "data"),
        prevent_initial_call=True,
    )
    def run_action(
        _clicks: list[int] | None,
        actor: str | None,
        role: str | None,
        token: int | None,
    ) -> tuple[Any, Any]:
        action_id = ctx.triggered_id
        if not isinstance(action_id, dict):
            return no_update, no_update
        try:
            message = perform_dashboard_action(
                action_id,
                actor=actor or "dashboard",
                role=role,
                settings=settings,
            )
        except ConsoleApiError as exc:
            return error_notice("Action failed", str(exc)), no_update
        return _success_notice(message), (token or 0) + 1


def perform_dashboard_action(
    action_id: dict[str, Any],
    *,
    actor: str,
    role: str | None,
    settings: Settings,
    client: ConsoleApiClient | None = None,
    client_factory: type[httpx.Client] = httpx.Client,
) -> str:
    normalized_role = normalize_role(role)
    if normalized_role not in MUTATING_ROLES:
        raise ConsoleApiError("viewer role cannot perform dashboard mutations", status_code=403)

    api = client or ConsoleApiClient.from_settings(
        settings,
        actor=actor,
        role=normalized_role,
        client_factory=client_factory,
    )
    kind = str(action_id.get("kind") or "")
    action = str(action_id.get("action") or "")
    target_id = str(action_id.get("target_id") or "")
    if not kind or not action or not target_id:
        raise ConsoleApiError("dashboard action is missing a target", status_code=400)

    if kind == "review":
        payload = {
            "version": _int(action_id.get("version")),
            "reason_code": f"dashboard_{action}",
            "reason": "Sprint 12 dashboard review action.",
            "policy_snapshot_hash": action_id.get("policy_hash"),
            "evidence_snapshot": {},
            "target_scope": "crm_export",
        }
        api.post(
            f"/v1/review/candidates/{target_id}/{action}",
            payload=payload,
            idempotency_key=idempotency_key(f"review-{action}", target_id),
        )
        return f"Review candidate {target_id} {action}d."

    if kind == "bulk-review":
        candidate_ids = [candidate_id for candidate_id in target_id.split(",") if candidate_id]
        if not candidate_ids:
            raise ConsoleApiError("bulk review requires at least one candidate", status_code=400)
        decision = "approved" if action == "approve" else "rejected"
        payload = {
            "candidate_ids": candidate_ids,
            "decision": decision,
            "candidate_versions": action_id.get("version") or {},
            "reason_code": f"dashboard_bulk_{action}",
            "reason": "Sprint 12 dashboard bulk review action.",
            "policy_snapshot_hash": action_id.get("policy_hash"),
            "evidence_snapshot": {},
        }
        api.post(
            "/v1/review/candidates/bulk-decision",
            payload=payload,
            idempotency_key=idempotency_key(f"bulk-review-{action}"),
        )
        return f"Bulk review {action} submitted for {len(candidate_ids)} candidate(s)."

    if kind == "crm-export":
        api.post(
            "/v1/crm/exports",
            payload={
                "crm_target_ids": [target_id],
                "provider": "attio",
                "reason": "Sprint 12 dashboard export action.",
            },
            idempotency_key=idempotency_key("crm-export", target_id),
        )
        return f"CRM export started for target {target_id}."

    if kind == "crm-retry":
        api.post(
            f"/v1/crm/exports/{target_id}/retry-failed",
            payload={"item_ids": []},
            idempotency_key=idempotency_key("crm-retry", target_id),
        )
        return f"Retry requested for CRM export batch {target_id}."

    if kind == "incident":
        return _perform_incident_action(api, action, target_id, action_id)

    if kind == "watch":
        api.patch(
            f"/v1/intelligence/watch-targets/{target_id}",
            payload={
                "enabled": bool(action_id.get("enabled")),
                "version": _int(action_id.get("version")),
            },
            idempotency_key=idempotency_key("watch-toggle", target_id),
        )
        state = "enabled" if action_id.get("enabled") else "paused"
        return f"Watch target {target_id} {state}."

    if kind == "sequence":
        if action not in {"pause", "resume", "cancel"}:
            raise ConsoleApiError(f"unsupported sequence action {action}", status_code=400)
        api.post(
            f"/v1/sequences/enrollments/{target_id}/{action}",
            payload={"reason": f"Sprint 12 dashboard {action} action."},
        )
        return f"Sequence enrollment {target_id} {action} requested."

    if kind == "meeting":
        return _perform_meeting_action(api, action, target_id)

    raise ConsoleApiError(f"unsupported dashboard action {kind}", status_code=400)


def _perform_incident_action(
    api: ConsoleApiClient,
    action: str,
    target_id: str,
    action_id: dict[str, Any],
) -> str:
    if action == "promote":
        api.post(
            f"/v1/intelligence/incidents/{target_id}/promote-to-watchlist",
            payload={},
            idempotency_key=idempotency_key("incident-watch", target_id),
        )
        return f"Incident {target_id} promoted to watchlist."
    if action in {"corroborate", "reject"}:
        version = action_id.get("version")
        if version is None:
            raise ConsoleApiError("incident action requires an optimistic version", status_code=409)
        path_action = "corroborate" if action == "corroborate" else "reject"
        payload = {
            "version": _int(version),
            "reason_code": f"dashboard_incident_{action}",
            "reason": "Sprint 12 dashboard incident decision.",
            "evidence_snapshot": {},
            "policy_snapshot": {},
        }
        api.post(
            f"/v1/governance/incidents/{target_id}/{path_action}",
            payload=payload,
            idempotency_key=idempotency_key(f"incident-{action}", target_id),
        )
        return f"Incident {target_id} {action} action submitted."
    raise ConsoleApiError(f"unsupported incident action {action}", status_code=400)


def _perform_meeting_action(api: ConsoleApiClient, action: str, target_id: str) -> str:
    if action == "prep":
        api.post(
            f"/v1/meetings/{target_id}/prep-packet",
            payload={},
            idempotency_key=idempotency_key("meeting-prep", target_id),
        )
        return f"Prep packet requested for meeting {target_id}."
    if action == "outcome":
        api.post(
            f"/v1/meetings/{target_id}/outcome",
            payload={
                "outcome_status": "completed",
                "outcome_notes": "Recorded from Sprint 12 dashboard.",
                "next_steps": [],
                "follow_up_tasks": [],
            },
            idempotency_key=idempotency_key("meeting-outcome", target_id),
        )
        return f"Outcome recorded for meeting {target_id}."
    if action == "cancel":
        api.post(
            f"/v1/meetings/{target_id}/cancel",
            payload={"reason": "Sprint 12 dashboard cancellation."},
        )
        return f"Cancel requested for meeting {target_id}."
    if action == "retry-sync":
        api.post(f"/v1/meetings/{target_id}/retry-sync", payload={})
        return f"CRM sync retry requested for meeting {target_id}."
    raise ConsoleApiError(f"unsupported meeting action {action}", status_code=400)


def _success_notice(message: str) -> html.Div:
    return html.Div([icon("check-circle"), html.Span(message)], className="success-notice")


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1
