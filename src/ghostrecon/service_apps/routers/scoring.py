from fastapi import Header

from ghostrecon.common.config import get_settings
from ghostrecon.models.api import (
    CandidateScoreOut,
    CandidateScoreRequest,
    ScoreRequest,
    SequenceEligibilityRequest,
)
from ghostrecon.services.scoring import (
    candidate_score_to_model,
    create_candidate_score,
    score_lead,
)
from ghostrecon.services.sequencing import (
    evaluate_sequence_eligibility,
)

from .registry import gateway_router, scoring_router, sequencing_router


@scoring_router.post("/v1/scoring/lead")
async def lead_score(request: ScoreRequest):
    return score_lead(request)


@gateway_router.post("/v1/scoring/candidates", response_model=CandidateScoreOut)
@scoring_router.post("/v1/scoring/candidates", response_model=CandidateScoreOut)
async def candidate_score(
    request: CandidateScoreRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> CandidateScoreOut:
    score = await create_candidate_score(
        request, idempotency_key=idempotency_key, settings=get_settings()
    )
    return candidate_score_to_model(score)


@gateway_router.post("/v1/sequences/evaluate")
@sequencing_router.post("/v1/sequences/evaluate")
async def sequence_eligibility(request: SequenceEligibilityRequest):
    return evaluate_sequence_eligibility(request)
