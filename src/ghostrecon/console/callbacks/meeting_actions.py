from ghostrecon.console.api import (
    ConsoleApiClient,
    ConsoleApiError,
    idempotency_key,
)


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
