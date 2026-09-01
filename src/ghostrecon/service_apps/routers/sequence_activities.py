from fastapi import HTTPException, Query

from ghostrecon.common.config import get_settings
from ghostrecon.models.api import (
    SequenceActivityActionRequest,
    SequenceActivityList,
    SequenceActivityOut,
    SequenceActivityScheduleMeetingRequest,
)
from ghostrecon.services.calendar_adapters import CalendarProviderError
from ghostrecon.services.sequencing import (
    complete_sequence_activity,
    get_sequence_activity,
    list_sequence_activities,
    schedule_sequence_meeting_activity,
    send_approved_sequence_email,
)

from .dependencies import VERIFIED_ACTOR
from .registry import gateway_router, sequencing_router


@gateway_router.get("/v1/sequences/activities", response_model=SequenceActivityList)
@sequencing_router.get("/v1/sequences/activities", response_model=SequenceActivityList)
async def sequence_activity_list(
    status: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> SequenceActivityList:
    return await list_sequence_activities(
        status=status,
        channel=channel,
        limit=limit,
        settings=get_settings(),
    )


@gateway_router.get("/v1/sequences/activities/{activity_id}", response_model=SequenceActivityOut)
@sequencing_router.get("/v1/sequences/activities/{activity_id}", response_model=SequenceActivityOut)
async def sequence_activity_detail(activity_id: str) -> SequenceActivityOut:
    activity = await get_sequence_activity(activity_id, settings=get_settings())
    if activity is None:
        raise HTTPException(status_code=404, detail="sequence activity not found")
    return activity


@gateway_router.post(
    "/v1/sequences/activities/{activity_id}/approve-email",
    response_model=SequenceActivityOut,
)
@sequencing_router.post(
    "/v1/sequences/activities/{activity_id}/approve-email",
    response_model=SequenceActivityOut,
)
async def sequence_activity_approve_email(
    activity_id: str,
    request: SequenceActivityActionRequest,
    actor: str = VERIFIED_ACTOR,
) -> SequenceActivityOut:
    try:
        activity = await send_approved_sequence_email(
            activity_id,
            request,
            actor=actor,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if activity is None:
        raise HTTPException(status_code=404, detail="sequence activity not found")
    return activity


@gateway_router.post(
    "/v1/sequences/activities/{activity_id}/complete",
    response_model=SequenceActivityOut,
)
@sequencing_router.post(
    "/v1/sequences/activities/{activity_id}/complete",
    response_model=SequenceActivityOut,
)
async def sequence_activity_complete(
    activity_id: str,
    request: SequenceActivityActionRequest,
    actor: str = VERIFIED_ACTOR,
) -> SequenceActivityOut:
    try:
        activity = await complete_sequence_activity(
            activity_id,
            request,
            actor=actor,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if activity is None:
        raise HTTPException(status_code=404, detail="sequence activity not found")
    return activity


@gateway_router.post(
    "/v1/sequences/activities/{activity_id}/schedule-meeting",
    response_model=SequenceActivityOut,
)
@sequencing_router.post(
    "/v1/sequences/activities/{activity_id}/schedule-meeting",
    response_model=SequenceActivityOut,
)
async def sequence_activity_schedule_meeting(
    activity_id: str,
    request: SequenceActivityScheduleMeetingRequest,
    actor: str = VERIFIED_ACTOR,
) -> SequenceActivityOut:
    try:
        activity = await schedule_sequence_meeting_activity(
            activity_id,
            request,
            actor=actor,
            settings=get_settings(),
        )
    except (CalendarProviderError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if activity is None:
        raise HTTPException(status_code=404, detail="sequence activity not found")
    return activity
