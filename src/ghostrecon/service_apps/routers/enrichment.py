from fastapi import Header, HTTPException, Query

from ghostrecon.common.config import get_settings
from ghostrecon.models.api import (
    ContactDomainDiscoveryResult,
    ContactEnrichmentCreate,
    ContactEnrichmentList,
    ContactEnrichmentOut,
    DomainEnrichmentRequest,
    EmailCandidatePersistResult,
    EntityResolutionCreate,
    EntityResolutionList,
    EntityResolutionOut,
    EventParticipantEnrichRequest,
    EventParticipantEnrichResult,
    WatchTargetContactDiscoveryResult,
)
from ghostrecon.services.enrichment import enrich_domain
from ghostrecon.services.enrichment_workflows import (
    contact_candidate_to_model,
    create_contact_enrichment_candidate,
    create_entity_resolution,
    discover_contact_candidate_domain,
    discover_contact_candidate_email,
    discover_watch_target_contacts,
    email_candidate_to_model,
    enrich_event_participant_target,
    entity_resolution_to_model,
    list_contact_enrichment_candidates,
    list_entity_resolutions,
)

from .dependencies import VERIFIED_ACTOR
from .registry import enrichment_router, gateway_router


@enrichment_router.post("/v1/enrichment/domain")
async def domain_enrichment(request: DomainEnrichmentRequest):
    return await enrich_domain(request.domain)


@gateway_router.post(
    "/v1/enrichment/watch-targets/{watch_target_id}/find-contact",
    response_model=WatchTargetContactDiscoveryResult,
)
@enrichment_router.post(
    "/v1/enrichment/watch-targets/{watch_target_id}/find-contact",
    response_model=WatchTargetContactDiscoveryResult,
)
async def enrichment_watch_target_find_contact(
    watch_target_id: str,
    actor: str = VERIFIED_ACTOR,
) -> WatchTargetContactDiscoveryResult:
    result = await discover_watch_target_contacts(
        watch_target_id,
        actor=actor,
        settings=get_settings(),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="watch target not found")
    return result


@gateway_router.post(
    "/v1/enrichment/contact-candidates/{candidate_id}/discover-domain",
    response_model=ContactDomainDiscoveryResult,
)
@enrichment_router.post(
    "/v1/enrichment/contact-candidates/{candidate_id}/discover-domain",
    response_model=ContactDomainDiscoveryResult,
)
async def enrichment_contact_candidate_discover_domain(
    candidate_id: str,
    actor: str = VERIFIED_ACTOR,
) -> ContactDomainDiscoveryResult:
    result = await discover_contact_candidate_domain(
        candidate_id,
        actor=actor,
        settings=get_settings(),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="contact candidate not found")
    return result


@gateway_router.post(
    "/v1/enrichment/contact-candidates/{candidate_id}/discover-email",
    response_model=EmailCandidatePersistResult,
)
@enrichment_router.post(
    "/v1/enrichment/contact-candidates/{candidate_id}/discover-email",
    response_model=EmailCandidatePersistResult,
)
async def enrichment_contact_candidate_discover_email(
    candidate_id: str,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> EmailCandidatePersistResult:
    records = await discover_contact_candidate_email(
        candidate_id,
        actor=actor,
        idempotency_key=idempotency_key,
        settings=get_settings(),
    )
    if records is None:
        raise HTTPException(status_code=404, detail="contact candidate not found")
    return EmailCandidatePersistResult(
        candidates=[email_candidate_to_model(record) for record in records]
    )


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
    origin_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> ContactEnrichmentList:
    candidates = await list_contact_enrichment_candidates(
        status=status,
        origin_type=origin_type,
        origin_id=origin_id,
        limit=limit,
        settings=get_settings(),
    )
    return ContactEnrichmentList(
        candidates=[contact_candidate_to_model(candidate) for candidate in candidates]
    )


@gateway_router.post(
    "/v1/enrichment/event-participants/{participant_id}/enrich-target",
    response_model=EventParticipantEnrichResult,
)
@enrichment_router.post(
    "/v1/enrichment/event-participants/{participant_id}/enrich-target",
    response_model=EventParticipantEnrichResult,
)
async def enrichment_event_participant_enrich_target(
    participant_id: str,
    request: EventParticipantEnrichRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> EventParticipantEnrichResult:
    try:
        return await enrich_event_participant_target(
            participant_id,
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
