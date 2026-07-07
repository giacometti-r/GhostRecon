from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response

from ghostrecon.common.config import get_settings
from ghostrecon.common.security import verify_attio_signature
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    BulkReviewDecisionRequest,
    BulkReviewDecisionResult,
    CalendarAvailabilityRequest,
    CalendarAvailabilityResult,
    CandidateScoreOut,
    CandidateScoreRequest,
    ContactEnrichmentCreate,
    ContactEnrichmentList,
    ContactEnrichmentOut,
    CrmExportBatchOut,
    CrmExportCreateRequest,
    CrmExportRetryRequest,
    CrmTargetList,
    CyberEventList,
    CyberEventOut,
    DashboardRole,
    DomainEnrichmentRequest,
    EmailCandidatePersistRequest,
    EmailCandidatePersistResult,
    EmailCandidateRequest,
    EmailVerifyBatchRequest,
    EmailVerifyBatchResult,
    EntityResolutionCreate,
    EntityResolutionList,
    EntityResolutionOut,
    EventParticipantList,
    EventParticipantOut,
    IncidentDecisionRequest,
    JobAccepted,
    MeetingActionRequest,
    MeetingCreateRequest,
    MeetingHandoffList,
    MeetingHandoffOut,
    MeetingOutcomeRequest,
    PrepPacketRequest,
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
    ReportingWatchTargetList,
    ReviewCandidateList,
    ReviewDecisionOut,
    ReviewDecisionRequest,
    ScoreRequest,
    SecurityIncidentList,
    SecurityIncidentOut,
    SequenceCreateRequest,
    SequenceEligibilityRequest,
    SequenceEnrollmentActionRequest,
    SequenceEnrollmentCreateRequest,
    SequenceEnrollmentList,
    SequenceEnrollmentOut,
    SequenceOut,
    SourceHealthList,
    SuppressionCheckRequest,
    SuppressionCreate,
    SuppressionOut,
    UnsubscribeRequest,
    WatchTargetCreate,
    WatchTargetList,
    WatchTargetOut,
    WatchTargetPatch,
)
from ghostrecon.services.calendar_adapters import CalendarProviderError
from ghostrecon.services.crm_exports import (
    get_crm_export_batch,
    retry_failed_crm_export_items,
    start_crm_export,
)
from ghostrecon.services.email_candidates import generate_email_candidates
from ghostrecon.services.enrichment import enrich_domain
from ghostrecon.services.enrichment_workflows import (
    contact_candidate_to_model,
    create_contact_enrichment_candidate,
    create_entity_resolution,
    email_candidate_to_model,
    entity_resolution_to_model,
    list_contact_enrichment_candidates,
    list_entity_resolutions,
    list_review_candidates,
    persist_email_candidates,
    review_candidate_to_model,
    verify_email_candidates,
)
from ghostrecon.services.event_intelligence import (
    event_to_api,
    get_event,
    list_events,
    list_participants,
    participant_to_api,
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
    review_decision_to_model,
    suppression_to_model,
)
from ghostrecon.services.incident_intelligence import (
    create_watch_target,
    get_incident,
    incident_to_api,
    list_incidents,
    list_watch_targets,
    patch_watch_target,
    promote_incident_to_watchlist,
    watch_target_to_api,
)
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
from ghostrecon.services.reporting import (
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
    get_reporting_watch_targets,
)
from ghostrecon.services.scoring import (
    candidate_score_to_model,
    create_candidate_score,
    score_lead,
)
from ghostrecon.services.sequencing import (
    cancel_sequence_enrollment,
    create_sequence,
    create_sequence_enrollment,
    evaluate_sequence_eligibility,
    get_sequence_enrollment,
    list_sequence_enrollments,
    pause_sequence_enrollment,
    process_unsubscribe,
    resume_sequence_enrollment,
)
from ghostrecon.services.source_registry import list_source_health

gateway_router = APIRouter(tags=["gateway"])
crm_router = APIRouter(tags=["crm"])
ingestion_router = APIRouter(tags=["ingestion"])
enrichment_router = APIRouter(tags=["enrichment"])
email_router = APIRouter(tags=["email-intelligence"])
scoring_router = APIRouter(tags=["scoring-routing"])
sequencing_router = APIRouter(tags=["sequencing"])
meeting_router = APIRouter(tags=["meeting-handoff"])
governance_router = APIRouter(tags=["governance"])
console_router = APIRouter(tags=["console"])
reporting_router = APIRouter(tags=["reporting"])
event_intelligence_router = APIRouter(tags=["event-intelligence"])
incident_intelligence_router = APIRouter(tags=["incident-intelligence"])


def reporting_operator_context(
    actor: str = Header(default="system", alias="X-Actor"),
    operator_role: str = Header(default=DashboardRole.VIEWER.value, alias="X-Operator-Role"),
) -> ReportingOperatorContext:
    try:
        role = DashboardRole(operator_role)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="unsupported operator role") from exc
    return ReportingOperatorContext(actor=actor, role=role)


REPORTING_OPERATOR_CONTEXT = Depends(reporting_operator_context)


@gateway_router.get("/v1/service-map")
async def service_map() -> dict[str, list[str]]:
    return {
        "services": sorted(ROUTERS.keys()),
        "core_flow": [
            "event-intelligence",
            "incident-intelligence",
            "ingestion",
            "enrichment",
            "email-intelligence",
            "scoring-routing",
            "governance",
            "sequencing",
            "meeting-handoff",
            "crm",
            "reporting",
        ],
    }


@gateway_router.get("/v1/intelligence/sources/health", response_model=SourceHealthList)
@reporting_router.get("/v1/intelligence/sources/health", response_model=SourceHealthList)
@event_intelligence_router.get("/v1/intelligence/sources/health", response_model=SourceHealthList)
async def source_health(kind: str | None = None) -> SourceHealthList:
    return SourceHealthList(sources=await list_source_health(kind, get_settings()))


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


@gateway_router.get(
    "/v1/reporting/incidents/{incident_id}", response_model=ReportingIncidentDetail
)
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


@gateway_router.get("/v1/intelligence/incidents/{incident_id}", response_model=SecurityIncidentOut)
@incident_intelligence_router.get(
    "/v1/intelligence/incidents/{incident_id}", response_model=SecurityIncidentOut
)
async def intelligence_incident_detail(incident_id: str) -> SecurityIncidentOut:
    incident = await get_incident(incident_id, get_settings())
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


@gateway_router.post("/v1/intelligence/watch-targets", response_model=WatchTargetOut)
@incident_intelligence_router.post("/v1/intelligence/watch-targets", response_model=WatchTargetOut)
async def intelligence_create_watch_target(
    payload: WatchTargetCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = Header(default="system", alias="X-Actor"),
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
    actor: str = Header(default="system", alias="X-Actor"),
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


@gateway_router.post(
    "/v1/intelligence/incidents/{incident_id}/promote-to-watchlist", response_model=WatchTargetOut
)
@incident_intelligence_router.post(
    "/v1/intelligence/incidents/{incident_id}/promote-to-watchlist", response_model=WatchTargetOut
)
async def intelligence_promote_incident_to_watchlist(
    incident_id: str,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = Header(default="system", alias="X-Actor"),
) -> WatchTargetOut:
    target = await promote_incident_to_watchlist(
        incident_id, actor=actor, idempotency_key=idempotency_key, settings=get_settings()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return WatchTargetOut.model_validate(watch_target_to_api(target))


@crm_router.post("/v1/crm/sync/account")
async def crm_sync_account(payload: dict[str, object]) -> dict[str, object]:
    event = new_event(
        event_name=EventName.CRM_SYNCED,
        aggregate_type="account",
        aggregate_id=str(payload.get("account_id") or payload.get("crm_account_id") or uuid4()),
        source_service="crm-service",
        payload=payload,
    )
    return {"status": "queued", "event": event.model_dump(mode="json")}


@gateway_router.post("/v1/crm/exports", response_model=CrmExportBatchOut)
@crm_router.post("/v1/crm/exports", response_model=CrmExportBatchOut)
async def crm_export_start(
    request: CrmExportCreateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = Header(default="system", alias="X-Actor"),
) -> CrmExportBatchOut:
    try:
        return await start_crm_export(
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@gateway_router.get("/v1/crm/exports/{batch_id}", response_model=CrmExportBatchOut)
@crm_router.get("/v1/crm/exports/{batch_id}", response_model=CrmExportBatchOut)
async def crm_export_detail(batch_id: str) -> CrmExportBatchOut:
    batch = await get_crm_export_batch(batch_id, settings=get_settings())
    if batch is None:
        raise HTTPException(status_code=404, detail="crm export batch not found")
    return batch


@gateway_router.post(
    "/v1/crm/exports/{batch_id}/retry-failed", response_model=CrmExportBatchOut
)
@crm_router.post(
    "/v1/crm/exports/{batch_id}/retry-failed", response_model=CrmExportBatchOut
)
async def crm_export_retry_failed(
    batch_id: str,
    request: CrmExportRetryRequest | None = None,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = Header(default="system", alias="X-Actor"),
) -> CrmExportBatchOut:
    try:
        batch = await retry_failed_crm_export_items(
            batch_id,
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if batch is None:
        raise HTTPException(status_code=404, detail="crm export batch not found")
    return batch


@ingestion_router.post("/webhooks/attio", status_code=202)
async def attio_webhook(
    request: Request,
    attio_signature: str | None = Header(default=None),
    x_attio_signature: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
) -> JobAccepted:
    settings = get_settings()
    body = await request.body()
    signature = attio_signature or x_attio_signature
    if not verify_attio_signature(body, signature, settings.attio_webhook_secret):
        return Response(status_code=401)  # type: ignore[return-value]
    # The worker stores and processes the raw payload. The API path must ACK quickly.
    _ = idempotency_key or str(uuid4())
    return JobAccepted(job_id=uuid4())


@enrichment_router.post("/v1/enrichment/domain")
async def domain_enrichment(request: DomainEnrichmentRequest):
    return await enrich_domain(request.domain)


@gateway_router.post("/v1/enrichment/entity-resolutions", response_model=EntityResolutionOut)
@enrichment_router.post("/v1/enrichment/entity-resolutions", response_model=EntityResolutionOut)
async def enrichment_create_entity_resolution(
    request: EntityResolutionCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> EntityResolutionOut:
    case = await create_entity_resolution(
        request, idempotency_key=idempotency_key, settings=get_settings()
    )
    return entity_resolution_to_model(case)


@gateway_router.get("/v1/enrichment/entity-resolutions", response_model=EntityResolutionList)
@enrichment_router.get("/v1/enrichment/entity-resolutions", response_model=EntityResolutionList)
async def enrichment_entity_resolutions(
    status: str | None = None,
    origin_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> EntityResolutionList:
    cases = await list_entity_resolutions(
        status=status, origin_type=origin_type, limit=limit, settings=get_settings()
    )
    return EntityResolutionList(cases=[entity_resolution_to_model(case) for case in cases])


@gateway_router.post("/v1/enrichment/contact-candidates", response_model=ContactEnrichmentOut)
@enrichment_router.post("/v1/enrichment/contact-candidates", response_model=ContactEnrichmentOut)
async def enrichment_create_contact_candidate(
    request: ContactEnrichmentCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ContactEnrichmentOut:
    candidate = await create_contact_enrichment_candidate(
        request, idempotency_key=idempotency_key, settings=get_settings()
    )
    return contact_candidate_to_model(candidate)


@gateway_router.get("/v1/enrichment/contact-candidates", response_model=ContactEnrichmentList)
@enrichment_router.get("/v1/enrichment/contact-candidates", response_model=ContactEnrichmentList)
async def enrichment_contact_candidates(
    status: str | None = None,
    origin_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> ContactEnrichmentList:
    candidates = await list_contact_enrichment_candidates(
        status=status, origin_type=origin_type, limit=limit, settings=get_settings()
    )
    return ContactEnrichmentList(
        candidates=[contact_candidate_to_model(candidate) for candidate in candidates]
    )


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


@gateway_router.post("/v1/sequences", response_model=SequenceOut)
@sequencing_router.post("/v1/sequences", response_model=SequenceOut)
async def sequence_create(
    request: SequenceCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: str = Header(default="system", alias="X-Actor"),
) -> SequenceOut:
    try:
        return await create_sequence(
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@gateway_router.post("/v1/sequences/enrollments", response_model=SequenceEnrollmentOut)
@sequencing_router.post("/v1/sequences/enrollments", response_model=SequenceEnrollmentOut)
async def sequence_enrollment_create(
    request: SequenceEnrollmentCreateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = Header(default="system", alias="X-Actor"),
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
    actor: str = Header(default="system", alias="X-Actor"),
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
    actor: str = Header(default="system", alias="X-Actor"),
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
    actor: str = Header(default="system", alias="X-Actor"),
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


@gateway_router.post("/v1/sequences/unsubscribe")
@sequencing_router.post("/v1/sequences/unsubscribe")
async def sequence_unsubscribe(
    request: UnsubscribeRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await process_unsubscribe(
        request,
        idempotency_key=idempotency_key,
        settings=get_settings(),
    )


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
    actor: str = Header(default="system", alias="X-Actor"),
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


@gateway_router.post(
    "/v1/meetings/{meeting_id}/prep-packet", response_model=MeetingHandoffOut
)
@meeting_router.post(
    "/v1/meetings/{meeting_id}/prep-packet", response_model=MeetingHandoffOut
)
async def meeting_generate_prep_packet(
    meeting_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: str = Header(default="system", alias="X-Actor"),
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
    actor: str = Header(default="system", alias="X-Actor"),
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
    actor: str = Header(default="system", alias="X-Actor"),
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
    actor: str = Header(default="system", alias="X-Actor"),
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


@gateway_router.post("/v1/suppressions", response_model=SuppressionOut)
@governance_router.post("/v1/suppressions", response_model=SuppressionOut)
async def suppression_create(
    request: SuppressionCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = Header(default="system", alias="X-Actor"),
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
    actor: str = Header(default="system", alias="X-Actor"),
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
    actor: str = Header(default="system", alias="X-Actor"),
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


@gateway_router.post(
    "/v1/review/candidates/bulk-decision", response_model=BulkReviewDecisionResult
)
@governance_router.post(
    "/v1/review/candidates/bulk-decision", response_model=BulkReviewDecisionResult
)
@console_router.post(
    "/v1/review/candidates/bulk-decision", response_model=BulkReviewDecisionResult
)
async def review_candidates_bulk_decision(
    request: BulkReviewDecisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = Header(default="system", alias="X-Actor"),
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
    actor: str = Header(default="system", alias="X-Actor"),
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
    actor: str = Header(default="system", alias="X-Actor"),
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


@gateway_router.get("/v1/kpis/catalog", response_model=ReportingKpiCatalog)
@reporting_router.get("/v1/kpis/catalog", response_model=ReportingKpiCatalog)
async def kpi_catalog(
    operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT,
) -> ReportingKpiCatalog:
    return await get_reporting_kpi_catalog(operator=operator, settings=get_settings())


ROUTERS = {
    "gateway-service": gateway_router,
    "crm-service": crm_router,
    "ingestion-service": ingestion_router,
    "enrichment-service": enrichment_router,
    "email-intelligence-service": email_router,
    "scoring-routing-service": scoring_router,
    "sequencing-service": sequencing_router,
    "meeting-handoff-service": meeting_router,
    "governance-service": governance_router,
    "console-service": console_router,
    "reporting-service": reporting_router,
    "event-intelligence-service": event_intelligence_router,
    "incident-intelligence-service": incident_intelligence_router,
}
