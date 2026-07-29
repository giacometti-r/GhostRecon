from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from ghostrecon.common.config import Settings
from ghostrecon.console.api import (
    ConsoleApiClient,
    ConsoleApiError,
    idempotency_key,
    normalize_role,
)

from .common import MUTATING_ROLES
from .incident_actions import _perform_incident_action
from .meeting_actions import _perform_meeting_action
from .values import _action_reason, _int, _version_map


def perform_dashboard_action(
    action_id: dict[str, Any],
    *,
    actor: str,
    role: str | None,
    settings: Settings,
    client: ConsoleApiClient | None = None,
    client_factory: type[httpx.Client] = httpx.Client,
    extra_payload: dict[str, Any] | None = None,
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
            "reason": "Dashboard analyst review action.",
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
            "candidate_versions": _version_map(action_id.get("version")),
            "reason_code": f"dashboard_bulk_{action}",
            "reason": "Dashboard analyst bulk review action.",
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
                "reason": "Dashboard CRM export action.",
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
        if action == "find-contact":
            result = api.post(
                f"/v1/enrichment/watch-targets/{target_id}/find-contact",
                payload={},
                idempotency_key=idempotency_key("watch-find-contact", target_id),
            )
            count = len(result.get("contact_candidates") or [])
            return f"Watch target {target_id} contact discovery returned {count} candidate(s)."
        if action != "toggle":
            raise ConsoleApiError(f"unsupported watch action {action}", status_code=400)
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

    if kind == "contact-candidate":
        if action == "discover-email":
            result = api.post(
                f"/v1/enrichment/contact-candidates/{target_id}/discover-email",
                payload={},
                idempotency_key=idempotency_key("contact-email", target_id),
            )
            count = len(result.get("candidates") or [])
            return (
                f"Contact candidate {target_id} email discovery returned {count} candidate(s)."
                if count
                else f"Contact candidate {target_id} routed to review for email discovery."
            )
        if action != "discover-domain":
            raise ConsoleApiError(f"unsupported contact candidate action {action}", status_code=400)
        result = api.post(
            f"/v1/enrichment/contact-candidates/{target_id}/discover-domain",
            payload={},
            idempotency_key=idempotency_key("contact-domain", target_id),
        )
        domain = result.get("discovered_domain")
        return (
            f"Contact candidate {target_id} domain discovered: {domain}."
            if domain
            else f"Contact candidate {target_id} routed to review for domain discovery."
        )

    if kind == "bulk-contact-candidate":
        candidate_ids = [candidate_id for candidate_id in target_id.split(",") if candidate_id]
        if not candidate_ids:
            raise ConsoleApiError("bulk discovery requires at least one candidate", status_code=400)
        endpoint = "discover-domain" if action == "discover-domain" else "discover-email"
        for candidate_id in candidate_ids:
            api.post(
                f"/v1/enrichment/contact-candidates/{candidate_id}/{endpoint}",
                payload={},
                idempotency_key=idempotency_key(f"contact-{endpoint}", candidate_id),
            )
        return f"Bulk {action.replace('-', ' ')} submitted for {len(candidate_ids)} candidate(s)."

    if kind == "sequence":
        if action not in {"pause", "resume", "cancel"}:
            raise ConsoleApiError(f"unsupported sequence action {action}", status_code=400)
        api.post(
            f"/v1/sequences/enrollments/{target_id}/{action}",
            payload={"reason": _action_reason(action, extra_payload)},
        )
        return f"Sequence enrollment {target_id} {action} requested."

    if kind == "sequence-definition":
        if action != "delete":
            raise ConsoleApiError(
                f"unsupported sequence definition action {action}", status_code=400
            )
        api.delete(f"/v1/sequences/{target_id}")
        return f"Sequence definition {target_id} deleted."

    if kind == "sequence-activity":
        if action == "approve-email":
            api.post(
                f"/v1/sequences/activities/{target_id}/approve-email",
                payload={"reason": _action_reason(action, extra_payload)},
            )
            return f"Sequence email activity {target_id} approved."
        if action == "complete":
            api.post(
                f"/v1/sequences/activities/{target_id}/complete",
                payload={"reason": _action_reason(action, extra_payload)},
            )
            return f"Sequence call activity {target_id} completed."
        if action == "schedule-meeting":
            start = datetime.now(UTC) + timedelta(days=1)
            end = start + timedelta(minutes=30)
            api.post(
                f"/v1/sequences/activities/{target_id}/schedule-meeting",
                payload={
                    "subject": "Security discovery",
                    "location": "Google Meet",
                    "start_at": start.isoformat(),
                    "end_at": end.isoformat(),
                    "timezone": "UTC",
                    "attendees": [],
                },
                idempotency_key=idempotency_key("sequence-meeting", target_id),
            )
            return f"Sequence meeting activity {target_id} scheduled."
        raise ConsoleApiError(f"unsupported sequence activity action {action}", status_code=400)

    if kind == "event-participant":
        domain = str((extra_payload or {}).get("domain") or "").strip()
        result = api.post(
            f"/v1/enrichment/event-participants/{target_id}/enrich-target",
            payload={"domain": domain} if domain else {},
            idempotency_key=idempotency_key("participant-enrichment-queue", target_id),
        )
        verified = result.get("verified_email")
        return (
            f"Participant {target_id} queued with {verified}."
            if verified
            else f"Participant {target_id} added to enrichment queue."
        )

    if kind == "meeting":
        return _perform_meeting_action(api, action, target_id)

    raise ConsoleApiError(f"unsupported dashboard action {kind}", status_code=400)
