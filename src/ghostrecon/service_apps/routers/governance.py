from fastapi import Header, HTTPException, Query

from ghostrecon.common.config import get_settings
from ghostrecon.models.api import (
    BulkReviewDecisionRequest,
    BulkReviewDecisionResult,
    CrmTargetList,
    CrmTargetOut,
    CrmTargetUpdateRequest,
    IncidentDecisionRequest,
    ReviewCandidateList,
    ReviewCandidateOut,
    ReviewCandidateUpdateRequest,
    ReviewDecisionOut,
    ReviewDecisionRequest,
    SuppressionCheckRequest,
    SuppressionCreate,
    SuppressionOut,
)
from ghostrecon.services.enrichment_workflows import (
    get_review_candidate,
    list_review_candidates,
    review_candidate_to_model,
    update_review_candidate,
)
from ghostrecon.services.governance import (
    approve_review_candidate,
    bulk_decide_review_candidates,
    corroborate_incident,
    create_suppression,
    crm_target_to_model,
    evaluate_suppression_with_store,
    list_crm_targets,
    reject_incident,
    reject_review_candidate,
    revert_incident,
    review_decision_to_model,
    suppression_to_model,
    update_crm_target,
)

from .dependencies import VERIFIED_ACTOR
from .registry import console_router, gateway_router, governance_router


@gateway_router.post("/v1/suppressions", response_model=SuppressionOut)
@governance_router.post("/v1/suppressions", response_model=SuppressionOut)
async def suppression_create(
    request: SuppressionCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> SuppressionOut:
    suppression = await create_suppression(
        request, actor=actor, idempotency_key=idempotency_key, settings=get_settings()
    )
    return suppression_to_model(suppression)


@gateway_router.post("/v1/suppressions/evaluate")
@governance_router.post("/v1/suppressions/evaluate")
async def suppression_check(request: SuppressionCheckRequest):
    return await evaluate_suppression_with_store(request, settings=get_settings())


@gateway_router.get("/v1/review/candidates", response_model=ReviewCandidateList)
@governance_router.get("/v1/review/candidates", response_model=ReviewCandidateList)
@console_router.get("/v1/review/candidates", response_model=ReviewCandidateList)
async def review_candidates(
    status: str | None = "open",
    candidate_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> ReviewCandidateList:
    candidates = await list_review_candidates(
        status=status, candidate_type=candidate_type, limit=limit, settings=get_settings()
    )
    return ReviewCandidateList(
        candidates=[review_candidate_to_model(candidate) for candidate in candidates]
    )


@gateway_router.get("/v1/review/candidates/{candidate_id}", response_model=ReviewCandidateOut)
@governance_router.get("/v1/review/candidates/{candidate_id}", response_model=ReviewCandidateOut)
@console_router.get("/v1/review/candidates/{candidate_id}", response_model=ReviewCandidateOut)
async def review_candidate_detail(candidate_id: str) -> ReviewCandidateOut:
    candidate = await get_review_candidate(candidate_id, settings=get_settings())
    if candidate is None:
        raise HTTPException(status_code=404, detail="review candidate not found")
    return review_candidate_to_model(candidate)


@gateway_router.patch("/v1/review/candidates/{candidate_id}", response_model=ReviewCandidateOut)
@governance_router.patch("/v1/review/candidates/{candidate_id}", response_model=ReviewCandidateOut)
@console_router.patch("/v1/review/candidates/{candidate_id}", response_model=ReviewCandidateOut)
async def review_candidate_update(
    candidate_id: str,
    request: ReviewCandidateUpdateRequest,
    actor: str = VERIFIED_ACTOR,
) -> ReviewCandidateOut:
    candidate = await update_review_candidate(
        candidate_id,
        request,
        actor=actor,
        settings=get_settings(),
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="review candidate not found")
    return review_candidate_to_model(candidate)


@gateway_router.post(
    "/v1/review/candidates/{candidate_id}/approve", response_model=ReviewDecisionOut
)
@governance_router.post(
    "/v1/review/candidates/{candidate_id}/approve", response_model=ReviewDecisionOut
)
@console_router.post(
    "/v1/review/candidates/{candidate_id}/approve", response_model=ReviewDecisionOut
)
async def review_candidate_approve(
    candidate_id: str,
    request: ReviewDecisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> ReviewDecisionOut:
    try:
        decision = await approve_review_candidate(
            candidate_id,
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if decision is None:
        raise HTTPException(status_code=404, detail="review candidate not found")
    return review_decision_to_model(decision)


@gateway_router.post(
    "/v1/review/candidates/{candidate_id}/reject", response_model=ReviewDecisionOut
)
@governance_router.post(
    "/v1/review/candidates/{candidate_id}/reject", response_model=ReviewDecisionOut
)
@console_router.post(
    "/v1/review/candidates/{candidate_id}/reject", response_model=ReviewDecisionOut
)
async def review_candidate_reject(
    candidate_id: str,
    request: ReviewDecisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> ReviewDecisionOut:
    try:
        decision = await reject_review_candidate(
            candidate_id,
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if decision is None:
        raise HTTPException(status_code=404, detail="review candidate not found")
    return review_decision_to_model(decision)


@gateway_router.post("/v1/review/candidates/bulk-decision", response_model=BulkReviewDecisionResult)
@governance_router.post(
    "/v1/review/candidates/bulk-decision", response_model=BulkReviewDecisionResult
)
@console_router.post("/v1/review/candidates/bulk-decision", response_model=BulkReviewDecisionResult)
async def review_candidates_bulk_decision(
    request: BulkReviewDecisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> BulkReviewDecisionResult:
    try:
        decisions = await bulk_decide_review_candidates(
            request, actor=actor, idempotency_key=idempotency_key, settings=get_settings()
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return BulkReviewDecisionResult(
        decisions=[review_decision_to_model(decision) for decision in decisions]
    )


@gateway_router.get("/v1/review/crm-targets", response_model=CrmTargetList)
@governance_router.get("/v1/review/crm-targets", response_model=CrmTargetList)
@console_router.get("/v1/review/crm-targets", response_model=CrmTargetList)
async def review_crm_targets(
    status: str | None = None,
    target_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> CrmTargetList:
    targets = await list_crm_targets(
        status=status, target_type=target_type, limit=limit, settings=get_settings()
    )
    return CrmTargetList(crm_targets=[crm_target_to_model(target) for target in targets])


@gateway_router.patch("/v1/review/crm-targets/{crm_target_id}", response_model=CrmTargetOut)
@governance_router.patch("/v1/review/crm-targets/{crm_target_id}", response_model=CrmTargetOut)
@console_router.patch("/v1/review/crm-targets/{crm_target_id}", response_model=CrmTargetOut)
async def review_crm_target_update(
    crm_target_id: str,
    request: CrmTargetUpdateRequest,
    actor: str = VERIFIED_ACTOR,
) -> CrmTargetOut:
    target = await update_crm_target(
        crm_target_id,
        request,
        actor=actor,
        settings=get_settings(),
    )
    if target is None:
        raise HTTPException(status_code=404, detail="crm target not found")
    return crm_target_to_model(target)


@gateway_router.post(
    "/v1/governance/incidents/{incident_id}/corroborate", response_model=ReviewDecisionOut
)
@governance_router.post(
    "/v1/governance/incidents/{incident_id}/corroborate", response_model=ReviewDecisionOut
)
async def governance_corroborate_incident(
    incident_id: str,
    request: IncidentDecisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> ReviewDecisionOut:
    try:
        decision = await corroborate_incident(
            incident_id,
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if decision is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return review_decision_to_model(decision)


@gateway_router.post(
    "/v1/governance/incidents/{incident_id}/reject", response_model=ReviewDecisionOut
)
@governance_router.post(
    "/v1/governance/incidents/{incident_id}/reject", response_model=ReviewDecisionOut
)
async def governance_reject_incident(
    incident_id: str,
    request: IncidentDecisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> ReviewDecisionOut:
    try:
        decision = await reject_incident(
            incident_id,
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if decision is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return review_decision_to_model(decision)


@gateway_router.post(
    "/v1/governance/incidents/{incident_id}/revert", response_model=ReviewDecisionOut
)
@governance_router.post(
    "/v1/governance/incidents/{incident_id}/revert", response_model=ReviewDecisionOut
)
async def governance_revert_incident(
    incident_id: str,
    request: IncidentDecisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> ReviewDecisionOut:
    try:
        decision = await revert_incident(
            incident_id,
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if decision is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return review_decision_to_model(decision)
