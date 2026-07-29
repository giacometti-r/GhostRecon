from __future__ import annotations

from ghostrecon.common.config import Settings
from ghostrecon.common.configuration import RuntimeProfile
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    EmailCandidatePersistRequest,
    EmailVerifyBatchRequest,
)
from ghostrecon.models.db import (
    ContactEnrichmentCandidate,
    EmailCandidateRecord,
)
from ghostrecon.services.email_verifier import EmailVerifierClient


async def persist_email_candidates(
    payload: EmailCandidatePersistRequest,
    *,
    idempotency_key: str,
    settings: Settings | None = None,
) -> list[EmailCandidateRecord]:
    async with session_scope(settings) as session:
        return await EnrichmentWorkflowRepository(session).persist_email_candidates(
            payload, idempotency_key
        )


async def discover_contact_candidate_email(
    candidate_id: str,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> list[EmailCandidateRecord] | None:
    resolved = settings or Settings()
    async with session_scope(resolved) as session:
        repository = EnrichmentWorkflowRepository(session)
        candidate = await session.get(ContactEnrichmentCandidate, candidate_id)
        if candidate is None:
            return None
        if not candidate.domain:
            inferred = (
                inferred_demo_domain(candidate.organization, candidate.published_name)
                if resolved.profile == RuntimeProfile.LOCAL
                else None
            )
            if inferred:
                candidate.domain = inferred
                candidate.status = "eligible"
                candidate.review_reason = None
                candidate.eligibility_reason = None
                candidate.version += 1
            else:
                await repository._mark_candidate_for_review(
                    candidate,
                    actor=actor,
                    reason_code="email_discovery_missing_domain",
                    reason="Email discovery needs a company domain.",
                )
                return []
        if candidate.status == "eligible" and candidate.contact_id is None:
            contact = await repository._upsert_contact(candidate)
            candidate.contact_id = contact.id
        try:
            records = await repository.persist_email_candidates(
                EmailCandidatePersistRequest(
                    contact_candidate_id=candidate.id,
                    full_name=candidate.published_name,
                    domain=candidate.domain,
                ),
                idempotency_key,
            )
        except ValueError:
            await repository._mark_candidate_for_review(
                candidate,
                actor=actor,
                reason_code="email_discovery_failed",
                reason="Email discovery could not generate usable candidates.",
            )
            return []
        if records:
            candidate.candidate_payload = {
                **dict(candidate.candidate_payload or {}),
                "email_candidate_count": len(records),
                "verified_email": records[0].email,
                "verified_email_status": records[0].verification_status,
            }
            candidate.version += 1
        return records


async def verify_email_candidates(
    payload: EmailVerifyBatchRequest,
    *,
    settings: Settings | None = None,
) -> list[EmailCandidateRecord]:
    async with session_scope(settings) as session:
        verifier = EmailVerifierClient(settings or Settings())
        return await EnrichmentWorkflowRepository(session).verify_email_candidates(
            payload, verifier
        )


from .policy import inferred_demo_domain  # noqa: E402
from .repository import EnrichmentWorkflowRepository  # noqa: E402
