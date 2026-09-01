from fastapi import Header, HTTPException, Query

from ghostrecon.common.config import get_settings
from ghostrecon.models.api import (
    SequenceCrmProspectImportRequest,
    SequenceEmailAlertCreate,
    SequenceEmailAlertOut,
    SequenceEnrollmentActionRequest,
    SequenceEnrollmentCreateRequest,
    SequenceEnrollmentList,
    SequenceEnrollmentOut,
)
from ghostrecon.services.sequencing import (
    cancel_sequence_enrollment,
    create_sequence_email_alert,
    create_sequence_enrollment,
    get_sequence_enrollment,
    import_crm_prospect_to_sequence,
    list_sequence_enrollments,
    pause_sequence_enrollment,
    resume_sequence_enrollment,
)

from .dependencies import VERIFIED_ACTOR
from .registry import gateway_router, sequencing_router


@gateway_router.post("/v1/sequences/enrollments", response_model=SequenceEnrollmentOut)
@sequencing_router.post("/v1/sequences/enrollments", response_model=SequenceEnrollmentOut)
async def sequence_enrollment_create(
    request: SequenceEnrollmentCreateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> SequenceEnrollmentOut:
    try:
        return await create_sequence_enrollment(
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@gateway_router.post(
    "/v1/sequences/enrollments/import-crm-prospect",
    response_model=SequenceEnrollmentOut,
)
@sequencing_router.post(
    "/v1/sequences/enrollments/import-crm-prospect",
    response_model=SequenceEnrollmentOut,
)
async def sequence_enrollment_import_crm_prospect(
    request: SequenceCrmProspectImportRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> SequenceEnrollmentOut:
    try:
        return await import_crm_prospect_to_sequence(
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@gateway_router.get("/v1/sequences/enrollments", response_model=SequenceEnrollmentList)
@sequencing_router.get("/v1/sequences/enrollments", response_model=SequenceEnrollmentList)
async def sequence_enrollment_list(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> SequenceEnrollmentList:
    return await list_sequence_enrollments(status=status, limit=limit, settings=get_settings())


@gateway_router.get(
    "/v1/sequences/enrollments/{enrollment_id}", response_model=SequenceEnrollmentOut
)
@sequencing_router.get(
    "/v1/sequences/enrollments/{enrollment_id}", response_model=SequenceEnrollmentOut
)
async def sequence_enrollment_detail(enrollment_id: str) -> SequenceEnrollmentOut:
    enrollment = await get_sequence_enrollment(enrollment_id, settings=get_settings())
    if enrollment is None:
        raise HTTPException(status_code=404, detail="sequence enrollment not found")
    return enrollment


@gateway_router.post(
    "/v1/sequences/enrollments/{enrollment_id}/pause", response_model=SequenceEnrollmentOut
)
@sequencing_router.post(
    "/v1/sequences/enrollments/{enrollment_id}/pause", response_model=SequenceEnrollmentOut
)
async def sequence_enrollment_pause(
    enrollment_id: str,
    request: SequenceEnrollmentActionRequest,
    actor: str = VERIFIED_ACTOR,
) -> SequenceEnrollmentOut:
    try:
        enrollment = await pause_sequence_enrollment(
            enrollment_id, request, actor=actor, settings=get_settings()
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if enrollment is None:
        raise HTTPException(status_code=404, detail="sequence enrollment not found")
    return enrollment


@gateway_router.post(
    "/v1/sequences/enrollments/{enrollment_id}/resume", response_model=SequenceEnrollmentOut
)
@sequencing_router.post(
    "/v1/sequences/enrollments/{enrollment_id}/resume", response_model=SequenceEnrollmentOut
)
async def sequence_enrollment_resume(
    enrollment_id: str,
    request: SequenceEnrollmentActionRequest,
    actor: str = VERIFIED_ACTOR,
) -> SequenceEnrollmentOut:
    try:
        enrollment = await resume_sequence_enrollment(
            enrollment_id, request, actor=actor, settings=get_settings()
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if enrollment is None:
        raise HTTPException(status_code=404, detail="sequence enrollment not found")
    return enrollment


@gateway_router.post(
    "/v1/sequences/enrollments/{enrollment_id}/cancel", response_model=SequenceEnrollmentOut
)
@sequencing_router.post(
    "/v1/sequences/enrollments/{enrollment_id}/cancel", response_model=SequenceEnrollmentOut
)
async def sequence_enrollment_cancel(
    enrollment_id: str,
    request: SequenceEnrollmentActionRequest,
    actor: str = VERIFIED_ACTOR,
) -> SequenceEnrollmentOut:
    try:
        enrollment = await cancel_sequence_enrollment(
            enrollment_id, request, actor=actor, settings=get_settings()
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if enrollment is None:
        raise HTTPException(status_code=404, detail="sequence enrollment not found")
    return enrollment


@gateway_router.post(
    "/v1/sequences/enrollments/{enrollment_id}/alerts",
    response_model=SequenceEmailAlertOut,
)
@sequencing_router.post(
    "/v1/sequences/enrollments/{enrollment_id}/alerts",
    response_model=SequenceEmailAlertOut,
)
async def sequence_enrollment_alert_create(
    enrollment_id: str,
    request: SequenceEmailAlertCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> SequenceEmailAlertOut:
    alert = await create_sequence_email_alert(
        enrollment_id,
        request,
        actor=actor,
        idempotency_key=idempotency_key,
        settings=get_settings(),
    )
    if alert is None:
        raise HTTPException(status_code=404, detail="sequence enrollment not found")
    return alert
