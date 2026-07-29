from __future__ import annotations

from datetime import datetime
from typing import Any

from ghostrecon.models.api import (
    ReviewDecisionOut,
)
from ghostrecon.models.db import (
    AuditEvent,
    OutboxEvent,
    ReviewCandidate,
    ReviewDecision,
)
from ghostrecon.services.scoring import policy_snapshot_hash


def review_decision_to_api(decision: ReviewDecision) -> dict[str, object]:
    return {
        "id": decision.id,
        "review_candidate_id": decision.review_candidate_id,
        "target_type": decision.target_type,
        "target_id": decision.target_id,
        "decision": decision.decision,
        "actor": decision.actor,
        "reason_code": decision.reason_code,
        "reason": decision.reason,
        "policy_snapshot_hash": decision.policy_snapshot_hash,
        "created_at": decision.created_at,
    }


def review_decision_to_model(decision: ReviewDecision) -> ReviewDecisionOut:
    return ReviewDecisionOut.model_validate(review_decision_to_api(decision))


def _create_decision(
    session: Any,
    *,
    review_candidate: ReviewCandidate | None,
    target_type: str,
    target_id: str,
    decision: str,
    actor: str,
    reason_code: str,
    reason: str | None,
    evidence_snapshot: dict[str, object],
    policy_snapshot: dict[str, object],
    idempotency_key: str,
) -> ReviewDecision:
    review_decision = ReviewDecision(
        review_candidate_id=review_candidate.id if review_candidate is not None else None,
        target_type=target_type,
        target_id=target_id,
        decision=decision,
        actor=actor,
        reason_code=reason_code,
        reason=reason,
        evidence_snapshot=_json_safe(evidence_snapshot),
        policy_snapshot=_json_safe(policy_snapshot),
        policy_snapshot_hash=policy_snapshot_hash(policy_snapshot),
        idempotency_key=idempotency_key,
    )
    session.add(review_decision)
    return review_decision


def _audit(
    session: Any,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    *,
    idempotency_key: str,
    payload: dict[str, object],
) -> None:
    session.add(
        AuditEvent(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            idempotency_key=idempotency_key,
            payload=_json_safe(payload),
        )
    )


def _enqueue_event(session: Any, event: Any) -> OutboxEvent:
    payload = event.model_dump(mode="json")
    outbox_event = OutboxEvent(
        event_name=payload["event_name"],
        aggregate_type=payload["aggregate_type"],
        aggregate_id=payload["aggregate_id"],
        idempotency_key=payload["idempotency_key"],
        payload=payload,
    )
    session.add(outbox_event)
    return outbox_event


def _json_safe(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
