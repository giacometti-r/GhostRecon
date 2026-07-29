from __future__ import annotations

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    CandidateScoreOut,
    CandidateScoreRequest,
    CandidateScoreRoute,
)
from ghostrecon.models.db import CandidateScore


async def create_candidate_score(
    request: CandidateScoreRequest,
    *,
    idempotency_key: str,
    settings: Settings | None = None,
) -> CandidateScore:
    async with session_scope(settings) as session:
        existing = await session.scalar(
            select(CandidateScore).where(CandidateScore.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing

        preview = score_candidate_preview(request)
        component_scores = {
            "fit": preview.fit_score,
            "relevance": preview.relevance_score,
            "recency": preview.recency_score,
            "confidence": preview.confidence_score,
            "evidence": preview.evidence_score,
            "policy_blockers": preview.policy_blockers,
        }
        score = CandidateScore(
            target_type=preview.target_type,
            target_id=preview.target_id,
            origin_type=preview.origin_type.value if preview.origin_type else None,
            origin_id=preview.origin_id,
            source_definition_id=request.source_definition_id,
            source_item_ids=list(request.source_item_ids),
            config_version=preview.config_version,
            component_scores=component_scores,
            composite_score=preview.composite_score,
            route=preview.route.value,
            reasons=list(preview.reasons),
            policy_snapshot=dict(request.policy_snapshot),
            policy_snapshot_hash=preview.policy_snapshot_hash,
            idempotency_key=idempotency_key,
        )
        session.add(score)
        await session.flush()

        _enqueue_event(
            session,
            new_event(
                event_name=EventName.LEAD_SCORED,
                aggregate_type="candidate_score",
                aggregate_id=score.id,
                source_service="scoring-routing-service",
                source_definition_id=request.source_definition_id,
                source_item_ids=request.source_item_ids,
                payload=candidate_score_to_api(score),
                idempotency_key=f"lead.scored:{score.id}",
            ),
        )
        if preview.route != CandidateScoreRoute.REJECTED:
            await _request_score_review(session, request, score, preview)
        return score


def candidate_score_to_api(score: CandidateScore) -> dict[str, object]:
    components = score.component_scores or {}
    return {
        "id": score.id,
        "target_type": score.target_type,
        "target_id": score.target_id,
        "origin_type": score.origin_type,
        "origin_id": score.origin_id,
        "config_version": score.config_version,
        "fit_score": int(components.get("fit", 0)),
        "relevance_score": int(components.get("relevance", 0)),
        "recency_score": int(components.get("recency", 0)),
        "confidence_score": int(components.get("confidence", 0)),
        "evidence_score": int(components.get("evidence", 0)),
        "composite_score": score.composite_score,
        "route": score.route,
        "reasons": score.reasons or [],
        "policy_blockers": components.get("policy_blockers", []),
        "policy_snapshot_hash": score.policy_snapshot_hash,
        "created_at": score.created_at,
    }


def candidate_score_to_model(score: CandidateScore) -> CandidateScoreOut:
    return CandidateScoreOut.model_validate(candidate_score_to_api(score))


from .leads import score_candidate_preview  # noqa: E402
from .reviews import _enqueue_event, _request_score_review  # noqa: E402
