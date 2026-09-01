from fastapi import Header, HTTPException, Query

from ghostrecon.common.config import get_settings
from ghostrecon.models.api import (
    CyberEventList,
    CyberEventOut,
    EventParticipantCreate,
    EventParticipantList,
    EventParticipantOut,
    EventUpdateRequest,
    ManualEventCreate,
)
from ghostrecon.services.event_intelligence import (
    create_event_participant,
    create_manual_event,
    event_to_api,
    get_event,
    list_events,
    list_participants,
    participant_to_api,
    update_event,
)

from .dependencies import VERIFIED_ACTOR
from .registry import event_intelligence_router, gateway_router


@gateway_router.get("/v1/intelligence/events", response_model=CyberEventList)
@event_intelligence_router.get("/v1/intelligence/events", response_model=CyberEventList)
async def intelligence_events(
    series: str | None = None,
    source: str | None = None,
    country: str | None = None,
    event_format: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> CyberEventList:
    events = await list_events(
        series=series,
        source=source,
        country=country,
        event_format=event_format,
        limit=limit,
        settings=get_settings(),
    )
    return CyberEventList(
        events=[CyberEventOut.model_validate(event_to_api(event)) for event in events]
    )


@gateway_router.post("/v1/intelligence/events/manual", response_model=CyberEventOut)
@event_intelligence_router.post("/v1/intelligence/events/manual", response_model=CyberEventOut)
async def intelligence_create_manual_event(
    request: ManualEventCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> CyberEventOut:
    try:
        event = await create_manual_event(
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CyberEventOut.model_validate(event_to_api(event))


@gateway_router.patch("/v1/intelligence/events/{event_id}", response_model=CyberEventOut)
@event_intelligence_router.patch("/v1/intelligence/events/{event_id}", response_model=CyberEventOut)
async def intelligence_patch_event(
    event_id: str,
    request: EventUpdateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> CyberEventOut:
    try:
        event = await update_event(
            event_id,
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return CyberEventOut.model_validate(event_to_api(event))


@gateway_router.get("/v1/intelligence/events/{event_id}", response_model=CyberEventOut)
@event_intelligence_router.get("/v1/intelligence/events/{event_id}", response_model=CyberEventOut)
async def intelligence_event_detail(event_id: str) -> CyberEventOut:
    event = await get_event(event_id, get_settings())
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return CyberEventOut.model_validate(event_to_api(event))


@gateway_router.get(
    "/v1/intelligence/events/{event_id}/participants", response_model=EventParticipantList
)
@event_intelligence_router.get(
    "/v1/intelligence/events/{event_id}/participants", response_model=EventParticipantList
)
async def intelligence_event_participants(
    event_id: str,
    reuse_state: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> EventParticipantList:
    event = await get_event(event_id, get_settings())
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    participants = await list_participants(
        event_id=event_id, reuse_state=reuse_state, limit=limit, settings=get_settings()
    )
    return EventParticipantList(
        participants=[
            EventParticipantOut.model_validate(participant_to_api(participant))
            for participant in participants
        ]
    )


@gateway_router.post(
    "/v1/intelligence/events/{event_id}/participants",
    response_model=EventParticipantOut,
)
@event_intelligence_router.post(
    "/v1/intelligence/events/{event_id}/participants",
    response_model=EventParticipantOut,
)
async def intelligence_create_event_participant(
    event_id: str,
    request: EventParticipantCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> EventParticipantOut:
    participant = await create_event_participant(
        event_id,
        request,
        actor=actor,
        idempotency_key=idempotency_key,
        settings=get_settings(),
    )
    if participant is None:
        raise HTTPException(status_code=404, detail="event not found")
    return EventParticipantOut.model_validate(participant_to_api(participant))


@gateway_router.get("/v1/intelligence/participants", response_model=EventParticipantList)
@event_intelligence_router.get("/v1/intelligence/participants", response_model=EventParticipantList)
async def intelligence_participants(
    event_id: str | None = None,
    reuse_state: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> EventParticipantList:
    participants = await list_participants(
        event_id=event_id, reuse_state=reuse_state, limit=limit, settings=get_settings()
    )
    return EventParticipantList(
        participants=[
            EventParticipantOut.model_validate(participant_to_api(participant))
            for participant in participants
        ]
    )
