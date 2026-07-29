from typing import Any

from ghostrecon.console.api import (
    ConsoleApiClient,
    ConsoleApiError,
    idempotency_key,
)

from .values import _int


def _perform_incident_action(
    api: ConsoleApiClient,
    action: str,
    target_id: str,
    action_id: dict[str, Any],
) -> str:
    if action == "promote":
        version = action_id.get("version")
        if version in (None, ""):
            raise ConsoleApiError("incident action requires an optimistic version", status_code=409)
        promoted_version = _int(version)
        if str(action_id.get("enabled") or "") == "candidate":
            payload = {
                "version": promoted_version,
                "method": "analyst_decision",
                "reason_code": "dashboard_incident_watchlist",
                "reason": "Dashboard watchlist promotion corroborated this incident.",
                "evidence_snapshot": {},
                "policy_snapshot": {},
            }
            api.post(
                f"/v1/governance/incidents/{target_id}/corroborate",
                payload=payload,
                idempotency_key=idempotency_key("incident-corroborate", target_id),
            )
            promoted_version += 1
        api.post(
            f"/v1/intelligence/incidents/{target_id}/promote-to-watchlist",
            payload={"version": promoted_version},
            idempotency_key=idempotency_key("incident-watch", target_id),
        )
        return f"Incident {target_id} added to watchlist."
    if action in {"corroborate", "reject", "revert"}:
        version = action_id.get("version")
        if version in (None, ""):
            raise ConsoleApiError("incident action requires an optimistic version", status_code=409)
        payload = {
            "version": _int(version),
            "reason_code": f"dashboard_incident_{action}",
            "reason": "Dashboard incident decision.",
            "evidence_snapshot": {},
            "policy_snapshot": {},
        }
        api.post(
            f"/v1/governance/incidents/{target_id}/{action}",
            payload=payload,
            idempotency_key=idempotency_key(f"incident-{action}", target_id),
        )
        return f"Incident {target_id} {action} action submitted."
    raise ConsoleApiError(f"unsupported incident action {action}", status_code=400)
