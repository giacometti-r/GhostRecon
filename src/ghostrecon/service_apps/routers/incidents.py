from fastapi import Header, HTTPException, Query

from ghostrecon.common.config import get_settings
from ghostrecon.models.api import (
    IncidentUpdateRequest,
    IncidentWatchPromotionRequest,
    ManualIncidentCreate,
    SecurityIncidentList,
    SecurityIncidentOut,
    WatchTargetCreate,
    WatchTargetList,
    WatchTargetOut,
    WatchTargetPatch,
)
from ghostrecon.services.incident_intelligence import (
    create_manual_incident,
    create_watch_target,
    get_incident,
    get_watch_target,
    incident_to_api,
    list_incidents,
    list_watch_targets,
    monitor_watch_targets,
    patch_watch_target,
    promote_incident_to_watchlist,
    update_incident,
    watch_target_to_api,
)

from .dependencies import VERIFIED_ACTOR
from .registry import gateway_router, incident_intelligence_router


@gateway_router.get("/v1/intelligence/incidents", response_model=SecurityIncidentList)
@incident_intelligence_router.get("/v1/intelligence/incidents", response_model=SecurityIncidentList)
async def intelligence_incidents(
    status: str | None = None,
    source: str | None = None,
    company: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> SecurityIncidentList:
    incidents = await list_incidents(
        status=status, source=source, company=company, limit=limit, settings=get_settings()
    )
    return SecurityIncidentList(
        incidents=[
            SecurityIncidentOut.model_validate(incident_to_api(incident)) for incident in incidents
        ]
    )


@gateway_router.post("/v1/intelligence/incidents/manual", response_model=SecurityIncidentList)
@incident_intelligence_router.post(
    "/v1/intelligence/incidents/manual", response_model=SecurityIncidentList
)
async def intelligence_create_manual_incident(
    request: ManualIncidentCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> SecurityIncidentList:
    incidents = await create_manual_incident(
        request,
        actor=actor,
        idempotency_key=idempotency_key,
        settings=get_settings(),
    )
    return SecurityIncidentList(
        incidents=[
            SecurityIncidentOut.model_validate(incident_to_api(incident)) for incident in incidents
        ]
    )


@gateway_router.get("/v1/intelligence/incidents/{incident_id}", response_model=SecurityIncidentOut)
@incident_intelligence_router.get(
    "/v1/intelligence/incidents/{incident_id}", response_model=SecurityIncidentOut
)
async def intelligence_incident_detail(incident_id: str) -> SecurityIncidentOut:
    incident = await get_incident(incident_id, get_settings())
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return SecurityIncidentOut.model_validate(incident_to_api(incident))


@gateway_router.patch(
    "/v1/intelligence/incidents/{incident_id}",
    response_model=SecurityIncidentOut,
)
@incident_intelligence_router.patch(
    "/v1/intelligence/incidents/{incident_id}",
    response_model=SecurityIncidentOut,
)
async def intelligence_patch_incident(
    incident_id: str,
    request: IncidentUpdateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> SecurityIncidentOut:
    try:
        incident = await update_incident(
            incident_id,
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return SecurityIncidentOut.model_validate(incident_to_api(incident))


@gateway_router.get("/v1/intelligence/watch-targets", response_model=WatchTargetList)
@incident_intelligence_router.get("/v1/intelligence/watch-targets", response_model=WatchTargetList)
async def intelligence_watch_targets(
    target_type: str | None = None,
    enabled: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> WatchTargetList:
    targets = await list_watch_targets(
        target_type=target_type, enabled=enabled, limit=limit, settings=get_settings()
    )
    return WatchTargetList(
        watch_targets=[
            WatchTargetOut.model_validate(watch_target_to_api(target)) for target in targets
        ]
    )


@gateway_router.get(
    "/v1/intelligence/watch-targets/{watch_target_id}", response_model=WatchTargetOut
)
@incident_intelligence_router.get(
    "/v1/intelligence/watch-targets/{watch_target_id}", response_model=WatchTargetOut
)
async def intelligence_watch_target_detail(watch_target_id: str) -> WatchTargetOut:
    target = await get_watch_target(watch_target_id, settings=get_settings())
    if target is None:
        raise HTTPException(status_code=404, detail="watch target not found")
    return WatchTargetOut.model_validate(watch_target_to_api(target))


@gateway_router.post("/v1/intelligence/watch-targets", response_model=WatchTargetOut)
@incident_intelligence_router.post("/v1/intelligence/watch-targets", response_model=WatchTargetOut)
async def intelligence_create_watch_target(
    payload: WatchTargetCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> WatchTargetOut:
    target = await create_watch_target(
        payload, actor=actor, idempotency_key=idempotency_key, settings=get_settings()
    )
    return WatchTargetOut.model_validate(watch_target_to_api(target))


@gateway_router.patch(
    "/v1/intelligence/watch-targets/{watch_target_id}", response_model=WatchTargetOut
)
@incident_intelligence_router.patch(
    "/v1/intelligence/watch-targets/{watch_target_id}", response_model=WatchTargetOut
)
async def intelligence_patch_watch_target(
    watch_target_id: str,
    payload: WatchTargetPatch,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> WatchTargetOut:
    try:
        target = await patch_watch_target(
            watch_target_id,
            payload,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if target is None:
        raise HTTPException(status_code=404, detail="watch target not found")
    return WatchTargetOut.model_validate(watch_target_to_api(target))


@gateway_router.post("/v1/intelligence/watch-targets/monitor", response_model=dict)
@incident_intelligence_router.post("/v1/intelligence/watch-targets/monitor", response_model=dict)
async def intelligence_monitor_watch_targets() -> dict[str, object]:
    return await monitor_watch_targets(settings=get_settings())


@gateway_router.post(
    "/v1/intelligence/incidents/{incident_id}/promote-to-watchlist", response_model=WatchTargetOut
)
@incident_intelligence_router.post(
    "/v1/intelligence/incidents/{incident_id}/promote-to-watchlist", response_model=WatchTargetOut
)
async def intelligence_promote_incident_to_watchlist(
    incident_id: str,
    request: IncidentWatchPromotionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> WatchTargetOut:
    try:
        target = await promote_incident_to_watchlist(
            incident_id,
            version=request.version,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if target is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return WatchTargetOut.model_validate(watch_target_to_api(target))
