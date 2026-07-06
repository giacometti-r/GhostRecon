from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse

from ghostrecon.common.config import get_settings
from ghostrecon.common.security import verify_attio_signature
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    ContactEnrichmentCreate,
    ContactEnrichmentList,
    ContactEnrichmentOut,
    CyberEventList,
    CyberEventOut,
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
    JobAccepted,
    PrepPacketRequest,
    ReviewCandidateList,
    ScoreRequest,
    SecurityIncidentList,
    SecurityIncidentOut,
    SequenceEligibilityRequest,
    SourceHealthList,
    SuppressionCheckRequest,
    WatchTargetCreate,
    WatchTargetList,
    WatchTargetOut,
    WatchTargetPatch,
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
from ghostrecon.services.governance import evaluate_suppression
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
from ghostrecon.services.meeting import build_prep_packet
from ghostrecon.services.scoring import score_lead
from ghostrecon.services.sequencing import evaluate_sequence_eligibility
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


@sequencing_router.post("/v1/sequences/evaluate")
async def sequence_eligibility(request: SequenceEligibilityRequest):
    return evaluate_sequence_eligibility(request)


@meeting_router.post("/v1/meetings/prep-packet")
async def prep_packet(request: PrepPacketRequest):
    return build_prep_packet(request)


@governance_router.post("/v1/suppressions/evaluate")
async def suppression_check(request: SuppressionCheckRequest):
    return evaluate_suppression(request)


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


@console_router.get("/", response_class=HTMLResponse)
async def console_home() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head><title>GhostRecon Console</title></head>
      <body>
        <h1>GhostRecon Console</h1>
        <p>Queues, approvals, replay controls, suppressions, and operational health live here.</p>
      </body>
    </html>
    """


@reporting_router.get("/v1/kpis/catalog")
async def kpi_catalog() -> dict[str, list[str]]:
    return {
        "coverage": ["accounts_touched_per_rep", "buying_group_coverage", "enrichment_rate"],
        "speed": ["trigger_to_first_touch_seconds", "meeting_to_prep_packet_seconds"],
        "quality": ["bounce_rate", "duplicate_rate", "routing_error_rate"],
        "pipeline": ["meeting_to_sql_rate", "sql_to_opportunity_rate", "pipeline_created"],
        "ops_health": ["workflow_failure_rate", "replay_rate", "mttr_seconds", "sla_breaches"],
    }


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
