from __future__ import annotations

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    BulkReviewDecisionRequest,
    ReviewDecisionAction,
    ReviewDecisionRequest,
)
from ghostrecon.models.db import (
    ReviewCandidate,
    ReviewDecision,
)


async def approve_review_candidate(
    candidate_id: str,
    request: ReviewDecisionRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> ReviewDecision | None:
    async with session_scope(settings) as session:
        existing = await _existing_decision(session, idempotency_key)
        if existing is not None:
            return existing
        candidate = await session.get(ReviewCandidate, candidate_id)
        if candidate is None:
            return None
        return await _approve_review_candidate_in_session(
            session, candidate, request, actor=actor, idempotency_key=idempotency_key
        )


async def reject_review_candidate(
    candidate_id: str,
    request: ReviewDecisionRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> ReviewDecision | None:
    async with session_scope(settings) as session:
        existing = await _existing_decision(session, idempotency_key)
        if existing is not None:
            return existing
        candidate = await session.get(ReviewCandidate, candidate_id)
        if candidate is None:
            return None
        return await _reject_review_candidate_in_session(
            session, candidate, request, actor=actor, idempotency_key=idempotency_key
        )


async def bulk_decide_review_candidates(
    request: BulkReviewDecisionRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> list[ReviewDecision]:
    async with session_scope(settings) as session:
        candidates = list(
            (
                await session.scalars(
                    select(ReviewCandidate).where(ReviewCandidate.id.in_(request.candidate_ids))
                )
            ).all()
        )
        if len(candidates) != len(set(request.candidate_ids)):
            raise ValueError("bulk decision includes unknown review candidate")
        candidate_types = {candidate.candidate_type for candidate in candidates}
        if len(candidate_types) != 1:
            raise ValueError("bulk decision requires one candidate type")
        if any(candidate.status != "open" for candidate in candidates):
            raise ValueError("bulk decision only supports open candidates")

        policy_hashes = {current_policy_hash(candidate) for candidate in candidates}
        if len(policy_hashes) != 1:
            raise ValueError("bulk decision requires one policy snapshot hash")
        if request.policy_snapshot_hash and policy_hashes != {request.policy_snapshot_hash}:
            raise ValueError("bulk decision policy snapshot hash mismatch")

        decisions: list[ReviewDecision] = []
        for candidate in candidates:
            version = request.candidate_versions.get(candidate.id)
            if version is None:
                raise ValueError("bulk decision missing candidate version")
            decision_request = ReviewDecisionRequest(
                version=version,
                reason_code=request.reason_code,
                reason=request.reason,
                policy_snapshot_hash=request.policy_snapshot_hash,
                evidence_snapshot=request.evidence_snapshot,
            )
            child_idempotency_key = f"{idempotency_key}:{candidate.id}"
            existing = await _existing_decision(session, child_idempotency_key)
            if existing is not None:
                decisions.append(existing)
                continue
            if request.decision == ReviewDecisionAction.APPROVED:
                decisions.append(
                    await _approve_review_candidate_in_session(
                        session,
                        candidate,
                        decision_request,
                        actor=actor,
                        idempotency_key=child_idempotency_key,
                    )
                )
            else:
                decisions.append(
                    await _reject_review_candidate_in_session(
                        session,
                        candidate,
                        decision_request,
                        actor=actor,
                        idempotency_key=child_idempotency_key,
                    )
                )
        return decisions


from .policy import current_policy_hash  # noqa: E402  # noqa: E402
from .review_repository import (  # noqa: E402
    _approve_review_candidate_in_session,
    _existing_decision,
    _reject_review_candidate_in_session,
)
