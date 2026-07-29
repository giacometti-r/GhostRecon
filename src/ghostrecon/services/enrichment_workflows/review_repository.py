from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.db import (
    OutboxEvent,
    ReviewCandidate,
)


class ReviewRepositoryMixin:
    async def list_review_candidates(
        self, *, status: str | None, candidate_type: str | None, limit: int
    ) -> list[ReviewCandidate]:
        stmt = select(ReviewCandidate).order_by(ReviewCandidate.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(ReviewCandidate.status == status)
        if candidate_type:
            stmt = stmt.where(ReviewCandidate.candidate_type == candidate_type)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def _request_review(
        self,
        *,
        candidate_type: str,
        target_type: str,
        target_id: str,
        origin_type: str | None,
        origin_id: str | None,
        source_definition_id: str | None,
        source_item_ids: list[object],
        reason_code: str,
        reason: str,
        evidence_summary: dict[str, object],
        policy_snapshot: dict[str, object],
    ) -> ReviewCandidate:
        idempotency_key = f"review:{candidate_type}:{target_id}:{reason_code}"
        existing = await self.session.scalar(
            select(ReviewCandidate).where(ReviewCandidate.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
        review = ReviewCandidate(
            candidate_type=candidate_type,
            target_type=target_type,
            target_id=target_id,
            origin_type=origin_type,
            origin_id=origin_id,
            source_definition_id=source_definition_id,
            source_item_ids=source_item_ids,
            reason_code=reason_code,
            reason=reason,
            evidence_summary=_json_safe(evidence_summary),
            policy_snapshot=_json_safe(policy_snapshot),
            idempotency_key=idempotency_key,
        )
        self.session.add(review)
        await self.session.flush()
        self._enqueue_event(
            new_event(
                event_name=EventName.APPROVAL_REQUESTED,
                aggregate_type="review_candidate",
                aggregate_id=review.id,
                source_service=REVIEW_SERVICE_NAME,
                source_definition_id=source_definition_id,
                source_item_ids=[str(item) for item in source_item_ids],
                payload={
                    "review_candidate_id": review.id,
                    "candidate_type": review.candidate_type,
                    "target_type": review.target_type,
                    "target_id": review.target_id,
                    "reason_code": review.reason_code,
                },
                idempotency_key=f"approval.requested:{review.id}",
            )
        )
        return review

    def _enqueue_event(self, event: Any) -> OutboxEvent:
        payload = event.model_dump(mode="json")
        outbox_event = OutboxEvent(
            event_name=payload["event_name"],
            aggregate_type=payload["aggregate_type"],
            aggregate_id=payload["aggregate_id"],
            idempotency_key=payload["idempotency_key"],
            payload=payload,
        )
        self.session.add(outbox_event)
        return outbox_event


from .policy import REVIEW_SERVICE_NAME, _json_safe  # noqa: E402
