from fastapi import Header, HTTPException, Query

from ghostrecon.common.config import get_settings
from ghostrecon.models.api import (
    CalendarAvailabilityRequest,
    CalendarAvailabilityResult,
    MeetingActionRequest,
    MeetingCreateRequest,
    MeetingHandoffList,
    MeetingHandoffOut,
    MeetingOutcomeRequest,
    PrepPacketRequest,
)
from ghostrecon.services.calendar_adapters import CalendarProviderError
from ghostrecon.services.meeting import (
    build_prep_packet,
    cancel_meeting,
    create_meeting,
    generate_meeting_prep_packet,
    get_calendar_availability,
    get_meeting,
    list_meetings,
    record_meeting_outcome,
    retry_meeting_crm_sync,
)

from .dependencies import VERIFIED_ACTOR
from .registry import gateway_router, meeting_router


@gateway_router.post("/v1/calendar/availability", response_model=CalendarAvailabilityResult)
@meeting_router.post("/v1/calendar/availability", response_model=CalendarAvailabilityResult)
async def calendar_availability(
    request: CalendarAvailabilityRequest,
) -> CalendarAvailabilityResult:
    try:
        return await get_calendar_availability(request, settings=get_settings())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CalendarProviderError as exc:
        raise HTTPException(
            status_code=503 if exc.retryable else 502,
            detail=str(exc),
        ) from exc


@gateway_router.post("/v1/meetings", response_model=MeetingHandoffOut)
@meeting_router.post("/v1/meetings", response_model=MeetingHandoffOut)
async def meeting_create(
    request: MeetingCreateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> MeetingHandoffOut:
    try:
        return await create_meeting(
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CalendarProviderError as exc:
        raise HTTPException(
            status_code=503 if exc.retryable else 502,
            detail=str(exc),
        ) from exc


@gateway_router.get("/v1/meetings", response_model=MeetingHandoffList)
@meeting_router.get("/v1/meetings", response_model=MeetingHandoffList)
async def meeting_list(
    status: str | None = None,
    crm_target_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> MeetingHandoffList:
    return await list_meetings(
        status=status,
        crm_target_id=crm_target_id,
        limit=limit,
        settings=get_settings(),
    )


@gateway_router.get("/v1/meetings/{meeting_id}", response_model=MeetingHandoffOut)
@meeting_router.get("/v1/meetings/{meeting_id}", response_model=MeetingHandoffOut)
async def meeting_detail(meeting_id: str) -> MeetingHandoffOut:
    meeting = await get_meeting(meeting_id, settings=get_settings())
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return meeting


@gateway_router.post("/v1/meetings/{meeting_id}/prep-packet", response_model=MeetingHandoffOut)
@meeting_router.post("/v1/meetings/{meeting_id}/prep-packet", response_model=MeetingHandoffOut)
async def meeting_generate_prep_packet(
    meeting_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> MeetingHandoffOut:
    meeting = await generate_meeting_prep_packet(
        meeting_id,
        actor=actor,
        idempotency_key=idempotency_key,
        settings=get_settings(),
    )
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return meeting


@gateway_router.post("/v1/meetings/{meeting_id}/outcome", response_model=MeetingHandoffOut)
@meeting_router.post("/v1/meetings/{meeting_id}/outcome", response_model=MeetingHandoffOut)
async def meeting_record_outcome(
    meeting_id: str,
    request: MeetingOutcomeRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> MeetingHandoffOut:
    meeting = await record_meeting_outcome(
        meeting_id,
        request,
        actor=actor,
        idempotency_key=idempotency_key,
        settings=get_settings(),
    )
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return meeting


@gateway_router.post("/v1/meetings/{meeting_id}/cancel", response_model=MeetingHandoffOut)
@meeting_router.post("/v1/meetings/{meeting_id}/cancel", response_model=MeetingHandoffOut)
async def meeting_cancel(
    meeting_id: str,
    request: MeetingActionRequest,
    actor: str = VERIFIED_ACTOR,
) -> MeetingHandoffOut:
    try:
        meeting = await cancel_meeting(
            meeting_id,
            request,
            actor=actor,
            settings=get_settings(),
        )
    except CalendarProviderError as exc:
        raise HTTPException(
            status_code=503 if exc.retryable else 502,
            detail=str(exc),
        ) from exc
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return meeting


@gateway_router.post("/v1/meetings/{meeting_id}/retry-sync", response_model=MeetingHandoffOut)
@meeting_router.post("/v1/meetings/{meeting_id}/retry-sync", response_model=MeetingHandoffOut)
async def meeting_retry_sync(
    meeting_id: str,
    actor: str = VERIFIED_ACTOR,
) -> MeetingHandoffOut:
    meeting = await retry_meeting_crm_sync(
        meeting_id,
        actor=actor,
        settings=get_settings(),
    )
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return meeting


@gateway_router.post("/v1/meetings/prep-packet")
@meeting_router.post("/v1/meetings/prep-packet")
async def prep_packet(request: PrepPacketRequest):
    return build_prep_packet(request)
