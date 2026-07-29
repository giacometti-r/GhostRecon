from fastapi import HTTPException, Query

from ghostrecon.common.config import get_settings
from ghostrecon.models.api import (
    ReportingCrmTargetDetail,
    ReportingCrmTargetList,
    ReportingEventDetail,
    ReportingEventList,
    ReportingIncidentDetail,
    ReportingIncidentList,
    ReportingKpiCatalog,
    ReportingMeetingDetail,
    ReportingMeetingList,
    ReportingOperatorContext,
    ReportingReviewQueue,
    ReportingSourceHealthList,
    ReportingWatchTargetDetail,
    ReportingWatchTargetList,
)
from ghostrecon.services.reporting import (
    get_reporting_crm_target_detail,
    get_reporting_crm_targets,
    get_reporting_event_detail,
    get_reporting_events,
    get_reporting_incident_detail,
    get_reporting_incidents,
    get_reporting_kpi_catalog,
    get_reporting_meeting_detail,
    get_reporting_meetings,
    get_reporting_review_queue,
    get_reporting_source_health,
    get_reporting_watch_target_detail,
    get_reporting_watch_targets,
)

from .dependencies import REPORTING_OPERATOR_CONTEXT
from .registry import gateway_router, reporting_router


@gateway_router.get("/v1/reporting/events", response_model=ReportingEventList)
@reporting_router.get("/v1/reporting/events", response_model=ReportingEventList)
async def reporting_events(
    series: str | None = None,
    source: str | None = None,
    country: str | None = None,
    event_format: str | None = None,
    topic: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingEventList:
    try:
        return await get_reporting_events(
            series=series,
            source=source,
            country=country,
            event_format=event_format,
            topic=topic,
            cursor=cursor,
            limit=limit,
            operator=operator,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@gateway_router.get("/v1/reporting/events/{event_id}", response_model=ReportingEventDetail)
@reporting_router.get("/v1/reporting/events/{event_id}", response_model=ReportingEventDetail)
async def reporting_event_detail(
    event_id: str,
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingEventDetail:
    detail = await get_reporting_event_detail(event_id, operator=operator, settings=get_settings())
    if detail is None:
        raise HTTPException(status_code=404, detail="event not found")
    return detail


@gateway_router.get("/v1/reporting/incidents", response_model=ReportingIncidentList)
@reporting_router.get("/v1/reporting/incidents", response_model=ReportingIncidentList)
async def reporting_incidents(
    status: str | None = None,
    source: str | None = None,
    company: str | None = None,
    attack_vector: str | None = None,
    incident_type: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingIncidentList:
    try:
        return await get_reporting_incidents(
            status=status,
            source=source,
            company=company,
            attack_vector=attack_vector,
            incident_type=incident_type,
            cursor=cursor,
            limit=limit,
            operator=operator,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@gateway_router.get("/v1/reporting/incidents/{incident_id}", response_model=ReportingIncidentDetail)
@reporting_router.get(
    "/v1/reporting/incidents/{incident_id}", response_model=ReportingIncidentDetail
)
async def reporting_incident_detail(
    incident_id: str,
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingIncidentDetail:
    detail = await get_reporting_incident_detail(
        incident_id, operator=operator, settings=get_settings()
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return detail


@gateway_router.get("/v1/reporting/watch-targets", response_model=ReportingWatchTargetList)
@reporting_router.get("/v1/reporting/watch-targets", response_model=ReportingWatchTargetList)
async def reporting_watch_targets(
    target_type: str | None = None,
    enabled: bool | None = None,
    owner: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingWatchTargetList:
    try:
        return await get_reporting_watch_targets(
            target_type=target_type,
            enabled=enabled,
            owner=owner,
            cursor=cursor,
            limit=limit,
            operator=operator,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@gateway_router.get(
    "/v1/reporting/watch-targets/{watch_target_id}",
    response_model=ReportingWatchTargetDetail,
)
@reporting_router.get(
    "/v1/reporting/watch-targets/{watch_target_id}",
    response_model=ReportingWatchTargetDetail,
)
async def reporting_watch_target_detail(
    watch_target_id: str,
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingWatchTargetDetail:
    detail = await get_reporting_watch_target_detail(
        watch_target_id,
        operator=operator,
        settings=get_settings(),
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="watch target not found")
    return detail


@gateway_router.get("/v1/reporting/review-queue", response_model=ReportingReviewQueue)
@reporting_router.get("/v1/reporting/review-queue", response_model=ReportingReviewQueue)
async def reporting_review_queue(
    status: str | None = "open",
    candidate_type: str | None = None,
    target_type: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingReviewQueue:
    try:
        return await get_reporting_review_queue(
            status=status,
            candidate_type=candidate_type,
            target_type=target_type,
            cursor=cursor,
            limit=limit,
            operator=operator,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@gateway_router.get("/v1/reporting/crm-targets", response_model=ReportingCrmTargetList)
@reporting_router.get("/v1/reporting/crm-targets", response_model=ReportingCrmTargetList)
async def reporting_crm_targets(
    status: str | None = None,
    target_type: str | None = None,
    export_status: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingCrmTargetList:
    try:
        return await get_reporting_crm_targets(
            status=status,
            target_type=target_type,
            export_status=export_status,
            cursor=cursor,
            limit=limit,
            operator=operator,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@gateway_router.get(
    "/v1/reporting/crm-targets/{crm_target_id}",
    response_model=ReportingCrmTargetDetail,
)
@reporting_router.get(
    "/v1/reporting/crm-targets/{crm_target_id}",
    response_model=ReportingCrmTargetDetail,
)
async def reporting_crm_target_detail(
    crm_target_id: str,
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingCrmTargetDetail:
    detail = await get_reporting_crm_target_detail(
        crm_target_id,
        operator=operator,
        settings=get_settings(),
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="crm target not found")
    return detail


@gateway_router.get("/v1/reporting/meetings", response_model=ReportingMeetingList)
@reporting_router.get("/v1/reporting/meetings", response_model=ReportingMeetingList)
async def reporting_meetings(
    status: str | None = None,
    crm_sync_status: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingMeetingList:
    try:
        return await get_reporting_meetings(
            status=status,
            crm_sync_status=crm_sync_status,
            cursor=cursor,
            limit=limit,
            operator=operator,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@gateway_router.get("/v1/reporting/meetings/{meeting_id}", response_model=ReportingMeetingDetail)
@reporting_router.get("/v1/reporting/meetings/{meeting_id}", response_model=ReportingMeetingDetail)
async def reporting_meeting_detail(
    meeting_id: str,
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingMeetingDetail:
    detail = await get_reporting_meeting_detail(
        meeting_id,
        operator=operator,
        settings=get_settings(),
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return detail


@gateway_router.get("/v1/reporting/source-health", response_model=ReportingSourceHealthList)
@reporting_router.get("/v1/reporting/source-health", response_model=ReportingSourceHealthList)
async def reporting_source_health(
    kind: str | None = None,
    freshness_status: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingSourceHealthList:
    try:
        return await get_reporting_source_health(
            kind=kind,
            freshness_status=freshness_status,
            cursor=cursor,
            limit=limit,
            operator=operator,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@gateway_router.get("/v1/reporting/kpis/catalog", response_model=ReportingKpiCatalog)
@reporting_router.get("/v1/reporting/kpis/catalog", response_model=ReportingKpiCatalog)
async def reporting_kpi_catalog(
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingKpiCatalog:
    return await get_reporting_kpi_catalog(operator=operator, settings=get_settings())


@gateway_router.get("/v1/kpis/catalog", response_model=ReportingKpiCatalog)
@reporting_router.get("/v1/kpis/catalog", response_model=ReportingKpiCatalog)
async def kpi_catalog(
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingKpiCatalog:
    return await get_reporting_kpi_catalog(operator=operator, settings=get_settings())
