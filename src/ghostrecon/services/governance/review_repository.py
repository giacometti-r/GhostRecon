from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    ReviewDecisionRequest,
)
from ghostrecon.models.db import (
    ReviewCandidate,
    ReviewDecision,
)


async def _approve_review_candidate_in_session(
    session: Any,
    candidate: ReviewCandidate,
    request: ReviewDecisionRequest,
    *,
    actor: str,
    idempotency_key: str,
) -> ReviewDecision:
    _validate_candidate_decision(candidate, request)
    blockers = review_policy_blockers(candidate)
    if blockers:
        raise ValueError("policy blockers: " + ", ".join(blockers))

    decision = _create_decision(
        session,
        review_candidate=candidate,
        target_type=candidate.target_type,
        target_id=candidate.target_id,
        decision="approved",
        actor=actor,
        reason_code=request.reason_code,
        reason=request.reason,
        evidence_snapshot=request.evidence_snapshot or candidate.evidence_summary or {},
        policy_snapshot=candidate.policy_snapshot or {},
        idempotency_key=idempotency_key,
    )
    candidate.status = "approved"
    candidate.version += 1
    await session.flush()

    _audit(
        session,
        actor,
        "review.approved",
        "review_candidate",
        candidate.id,
        idempotency_key=f"audit:{idempotency_key}",
        payload=review_decision_to_api(decision),
    )
    _enqueue_event(
        session,
        new_event(
            event_name=EventName.REVIEW_APPROVED,
            aggregate_type="review_candidate",
            aggregate_id=candidate.id,
            source_service="governance-service",
            source_definition_id=candidate.source_definition_id,
            source_item_ids=[str(item) for item in candidate.source_item_ids or []],
            payload=review_decision_to_api(decision),
            idempotency_key=f"review.approved:{decision.id}",
        ),
    )
    crm_target = _create_crm_target(session, candidate, decision)
    await session.flush()
    _enqueue_event(
        session,
        new_event(
            event_name=EventName.CRM_TARGET_CREATED,
            aggregate_type="crm_target",
            aggregate_id=crm_target.id,
            source_service="governance-service",
            source_definition_id=candidate.source_definition_id,
            source_item_ids=[str(item) for item in candidate.source_item_ids or []],
            payload=crm_target_to_api(crm_target),
            idempotency_key=f"crm_target.created:{crm_target.id}",
        ),
    )
    return decision


async def _reject_review_candidate_in_session(
    session: Any,
    candidate: ReviewCandidate,
    request: ReviewDecisionRequest,
    *,
    actor: str,
    idempotency_key: str,
) -> ReviewDecision:
    _validate_candidate_decision(candidate, request)
    decision = _create_decision(
        session,
        review_candidate=candidate,
        target_type=candidate.target_type,
        target_id=candidate.target_id,
        decision="rejected",
        actor=actor,
        reason_code=request.reason_code,
        reason=request.reason,
        evidence_snapshot=request.evidence_snapshot or candidate.evidence_summary or {},
        policy_snapshot=candidate.policy_snapshot or {},
        idempotency_key=idempotency_key,
    )
    candidate.status = "rejected"
    candidate.version += 1
    await session.flush()
    _audit(
        session,
        actor,
        "review.rejected",
        "review_candidate",
        candidate.id,
        idempotency_key=f"audit:{idempotency_key}",
        payload=review_decision_to_api(decision),
    )
    _enqueue_event(
        session,
        new_event(
            event_name=EventName.REVIEW_REJECTED,
            aggregate_type="review_candidate",
            aggregate_id=candidate.id,
            source_service="governance-service",
            source_definition_id=candidate.source_definition_id,
            source_item_ids=[str(item) for item in candidate.source_item_ids or []],
            payload=review_decision_to_api(decision),
            idempotency_key=f"review.rejected:{decision.id}",
        ),
    )
    return decision


def _validate_candidate_decision(
    candidate: ReviewCandidate, request: ReviewDecisionRequest
) -> None:
    if candidate.status != "open":
        raise ValueError("review candidate is not open")
    if candidate.version != request.version:
        raise ValueError("stale optimistic version")
    if request.policy_snapshot_hash and request.policy_snapshot_hash != current_policy_hash(
        candidate
    ):
        raise ValueError("policy snapshot hash mismatch")


async def _existing_decision(session: Any, idempotency_key: str) -> ReviewDecision | None:
    return await session.scalar(
        select(ReviewDecision).where(ReviewDecision.idempotency_key == idempotency_key)
    )


from .crm_targets import _create_crm_target, crm_target_to_api  # noqa: E402
from .policy import current_policy_hash, review_policy_blockers  # noqa: E402  # noqa: E402
from .review_records import (  # noqa: E402
    _audit,
    _create_decision,
    _enqueue_event,
    review_decision_to_api,
)
