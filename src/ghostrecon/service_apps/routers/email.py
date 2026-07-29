from fastapi import Header, HTTPException

from ghostrecon.common.config import get_settings
from ghostrecon.models.api import (
    EmailCandidatePersistRequest,
    EmailCandidatePersistResult,
    EmailCandidateRequest,
    EmailVerifyBatchRequest,
    EmailVerifyBatchResult,
)
from ghostrecon.services.email_candidates import generate_email_candidates
from ghostrecon.services.enrichment_workflows import (
    email_candidate_to_model,
    persist_email_candidates,
    verify_email_candidates,
)

from .registry import email_router, gateway_router


@email_router.post("/v1/email/candidates")
async def email_candidates(request: EmailCandidateRequest):
    return {
        "candidates": [
            candidate.model_dump(mode="json")
            for candidate in generate_email_candidates(
                request.full_name, request.domain, request.known_patterns
            )
        ]
    }


@gateway_router.post("/v1/email/candidates/persist", response_model=EmailCandidatePersistResult)
@email_router.post("/v1/email/candidates/persist", response_model=EmailCandidatePersistResult)
async def email_persist_candidates(
    request: EmailCandidatePersistRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> EmailCandidatePersistResult:
    try:
        candidates = await persist_email_candidates(
            request, idempotency_key=idempotency_key, settings=get_settings()
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return EmailCandidatePersistResult(
        candidates=[email_candidate_to_model(candidate) for candidate in candidates]
    )


@gateway_router.post("/v1/email/verify-batch", response_model=EmailVerifyBatchResult)
@email_router.post("/v1/email/verify-batch", response_model=EmailVerifyBatchResult)
async def email_verify_batch(request: EmailVerifyBatchRequest) -> EmailVerifyBatchResult:
    candidates = await verify_email_candidates(request, settings=get_settings())
    return EmailVerifyBatchResult(
        candidates=[email_candidate_to_model(candidate) for candidate in candidates]
    )


@email_router.post("/v1/email/verify")
async def email_verify(payload: dict[str, object]) -> dict[str, object]:
    return {"status": "queued", "provider": "umuterturk/email-verifier", "payload": payload}
