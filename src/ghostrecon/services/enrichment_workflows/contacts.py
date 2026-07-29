from __future__ import annotations

from ghostrecon.common.config import Settings
from ghostrecon.common.configuration import RuntimeProfile, assert_adapter_allowed
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    ContactDomainDiscoveryResult,
    ContactEnrichmentCreate,
    EmailCandidatePersistRequest,
    EmailVerifyBatchRequest,
    EventParticipantEnrichRequest,
    EventParticipantEnrichResult,
)
from ghostrecon.models.db import (
    ContactEnrichmentCandidate,
    EmailCandidateRecord,
    EventParticipant,
)
from ghostrecon.services.email_verifier import EmailVerifierClient
from ghostrecon.services.search_adapters import (
    official_website_query,
    search_provider_for_settings,
)


async def discover_contact_candidate_domain(
    candidate_id: str,
    *,
    actor: str,
    settings: Settings | None = None,
) -> ContactDomainDiscoveryResult | None:
    resolved = settings or Settings()
    provider = search_provider_for_settings(resolved)
    async with session_scope(resolved) as session:
        repository = EnrichmentWorkflowRepository(session)
        candidate = await session.get(ContactEnrichmentCandidate, candidate_id)
        if candidate is None:
            return None
        query_subject = candidate.organization or candidate.published_name
        if not query_subject:
            candidate.status = "needs_review"
            candidate.review_reason = "domain_discovery_missing_company"
            candidate.eligibility_reason = "domain_discovery_missing_company"
            candidate.version += 1
            return ContactDomainDiscoveryResult(
                contact_candidate=contact_candidate_to_model(candidate),
                query="",
                provider=provider.provider_name,
                selected_url=None,
                discovered_domain=None,
                status=candidate.status,
                review_reason=candidate.review_reason,
            )
        query = official_website_query(query_subject)
        results = await provider.search(query, limit=resolved.search_result_limit)
        selected = await repository.apply_domain_discovery(
            candidate,
            results,
            query=query,
            provider_name=provider.provider_name,
            actor=actor,
        )
        if candidate.domain is None and resolved.profile == RuntimeProfile.LOCAL:
            inferred = inferred_demo_domain(candidate.organization, candidate.published_name)
            if inferred:
                candidate.domain = inferred
                candidate.status = "eligible"
                candidate.review_reason = None
                candidate.eligibility_reason = None
                candidate.candidate_payload = {
                    **dict(candidate.candidate_payload or {}),
                    "domain_discovery": {
                        **dict((candidate.candidate_payload or {}).get("domain_discovery") or {}),
                        "selected_domain": inferred,
                        "fallback": "demo_inferred",
                    },
                }
                candidate.version += 1
        return ContactDomainDiscoveryResult(
            contact_candidate=contact_candidate_to_model(candidate),
            query=query,
            provider=provider.provider_name,
            selected_url=selected.url if selected else None,
            discovered_domain=candidate.domain,
            status=candidate.status,
            review_reason=candidate.review_reason,
        )


async def enrich_event_participant_target(
    participant_id: str,
    payload: EventParticipantEnrichRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
    verifier: EmailVerifierClient | None = None,
) -> EventParticipantEnrichResult:
    resolved = settings or Settings()
    if verifier is not None:
        assert_adapter_allowed(resolved, verifier, "email_verifier_provider")
    async with session_scope(resolved) as session:
        participant = await session.get(EventParticipant, participant_id)
        if participant is None:
            raise ValueError("event participant not found")
        repository = EnrichmentWorkflowRepository(session)
        source_item_ids = [participant.source_item_id] if participant.source_item_id else []
        domain = normalize_domain(payload.domain)
        if domain is None and resolved.profile == RuntimeProfile.LOCAL:
            domain = inferred_demo_domain(participant.organization, participant.published_name)
        contact_candidate = await repository.create_contact_candidate(
            ContactEnrichmentCreate(
                origin_type="event_participant",
                origin_id=participant.id,
                published_name=participant.published_name,
                organization=participant.organization,
                title=participant.published_role,
                role_scope=payload.role_scope,
                domain=domain,
                profile_url=participant.profile_url,
                source_url=participant.profile_url,
                reuse_state=participant.reuse_state,
                source_definition_id=participant.source_definition_id,
                source_item_ids=source_item_ids,
                policy_snapshot={
                    "participant_reuse_state": participant.reuse_state,
                    "contact_extraction_allowed": participant.contact_extraction_allowed,
                    "crm_export_allowed": participant.crm_export_allowed,
                },
                candidate_payload={
                    "source": "global_events",
                    "created_by": actor,
                    "cyber_event_id": participant.cyber_event_id,
                },
            ),
            f"{idempotency_key}:contact",
        )
        email_records: list[EmailCandidateRecord] = []
        if contact_candidate.status == "eligible" and domain:
            email_records = await repository.persist_email_candidates(
                EmailCandidatePersistRequest(
                    contact_candidate_id=contact_candidate.id,
                    full_name=participant.published_name,
                    domain=domain,
                ),
                f"{idempotency_key}:email",
            )
            if email_records:
                email_records = await repository.verify_email_candidates(
                    EmailVerifyBatchRequest(candidate_ids=[record.id for record in email_records]),
                    verifier or EmailVerifierClient(resolved),
                )
        verified = next(
            (record.email for record in email_records if record.verification_status == "verified"),
            None,
        )
        if verified:
            contact_candidate.candidate_payload = {
                **dict(contact_candidate.candidate_payload or {}),
                "verified_email": verified,
                "verified_email_status": "verified",
            }
        review_reason = contact_candidate.review_reason or contact_candidate.eligibility_reason
        if verified is None:
            review_reason = review_reason or next(
                (record.review_reason for record in email_records if record.review_reason),
                None,
            )
        return EventParticipantEnrichResult(
            contact_candidate=contact_candidate_to_model(contact_candidate),
            email_candidates=[email_candidate_to_model(record) for record in email_records],
            verified_email=verified,
            review_reason=review_reason,
        )


from .policy import inferred_demo_domain, normalize_domain  # noqa: E402
from .repository import EnrichmentWorkflowRepository  # noqa: E402
from .serializers import contact_candidate_to_model, email_candidate_to_model  # noqa: E402
