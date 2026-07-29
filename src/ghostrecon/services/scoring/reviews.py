from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    CandidateScoreOut,
    CandidateScoreRequest,
    CandidateScoreRoute,
)
from ghostrecon.models.db import CandidateScore, OutboxEvent, ReviewCandidate


def _route_for_score(score: int, policy_blockers: list[str]) -> CandidateScoreRoute:
    if policy_blockers or score < 40:
        return CandidateScoreRoute.REJECTED
    if score < 70:
        return CandidateScoreRoute.NEEDS_REVIEW
    return CandidateScoreRoute.CRM_TARGET_REVIEW


async def _request_score_review(
    session: Any,
    request: CandidateScoreRequest,
    score: CandidateScore,
    preview: CandidateScoreOut,
) -> ReviewCandidate:
    reason_code = (
        "score_ready_for_crm_target_review"
        if preview.route == CandidateScoreRoute.CRM_TARGET_REVIEW
        else "score_requires_review"
    )
    idempotency_key = f"review:scoring:{score.id}:{reason_code}"
    existing = await session.scalar(
        select(ReviewCandidate).where(ReviewCandidate.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing

    review = ReviewCandidate(
        candidate_type="scoring",
        target_type=request.target_type,
        target_id=request.target_id,
        origin_type=request.origin_type.value if request.origin_type else None,
        origin_id=request.origin_id,
        source_definition_id=request.source_definition_id,
        source_item_ids=list(request.source_item_ids),
        reason_code=reason_code,
        reason="Candidate score requires analyst review before CRM target creation.",
        evidence_summary={
            "candidate_score_id": score.id,
            "composite_score": preview.composite_score,
            "route": preview.route.value,
            "reasons": preview.reasons,
        },
        policy_snapshot=dict(request.policy_snapshot),
        policy_snapshot_hash=preview.policy_snapshot_hash,
        idempotency_key=idempotency_key,
    )
    session.add(review)
    await session.flush()
    _enqueue_event(
        session,
        new_event(
            event_name=EventName.APPROVAL_REQUESTED,
            aggregate_type="review_candidate",
            aggregate_id=review.id,
            source_service="scoring-routing-service",
            source_definition_id=request.source_definition_id,
            source_item_ids=request.source_item_ids,
            payload={
                "review_candidate_id": review.id,
                "candidate_score_id": score.id,
                "candidate_type": review.candidate_type,
                "target_type": review.target_type,
                "target_id": review.target_id,
                "reason_code": review.reason_code,
            },
            idempotency_key=f"approval.requested:{review.id}",
        ),
    )
    return review


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


def _optional_int(value: object, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _int_or_default(value: object, default: int = 0) -> int:
    coerced = _optional_int(value, default)
    if coerced is None:
        return default
    return coerced


def _clamp(value: int) -> int:
    return min(max(value, 0), 100)
