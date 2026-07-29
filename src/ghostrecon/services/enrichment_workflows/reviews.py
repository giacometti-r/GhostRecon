from __future__ import annotations

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    ReviewCandidateUpdateRequest,
)
from ghostrecon.models.db import (
    ReviewCandidate,
)


async def list_review_candidates(
    *,
    status: str | None = "open",
    candidate_type: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> list[ReviewCandidate]:
    async with session_scope(settings) as session:
        return await EnrichmentWorkflowRepository(session).list_review_candidates(
            status=status, candidate_type=candidate_type, limit=limit
        )


async def get_review_candidate(
    candidate_id: str,
    *,
    settings: Settings | None = None,
) -> ReviewCandidate | None:
    async with session_scope(settings) as session:
        return await session.get(ReviewCandidate, candidate_id)


async def update_review_candidate(
    candidate_id: str,
    payload: ReviewCandidateUpdateRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> ReviewCandidate | None:
    _ = actor
    async with session_scope(settings) as session:
        candidate = await session.get(ReviewCandidate, candidate_id)
        if candidate is None:
            return None
        evidence = dict(candidate.evidence_summary or {})
        candidate_payload = (
            dict(evidence.get("candidate_payload"))
            if isinstance(evidence.get("candidate_payload"), dict)
            else {}
        )
        fields = payload.model_fields_set
        if "name" in fields:
            _set_or_remove(evidence, "published_name", payload.name)
            _set_or_remove(candidate_payload, "published_name", payload.name)
        if "company" in fields:
            _set_or_remove(evidence, "organization", payload.company)
            _set_or_remove(candidate_payload, "company", payload.company)
        if "domain" in fields:
            _set_or_remove(evidence, "domain", payload.domain)
            _set_or_remove(candidate_payload, "domain", payload.domain)
        if "email" in fields:
            _set_or_remove(evidence, "email", payload.email)
            _set_or_remove(candidate_payload, "verified_email", payload.email)
            if payload.email:
                candidate_payload["verified_email_status"] = "dashboard_updated"
        if candidate_payload:
            evidence["candidate_payload"] = candidate_payload
        else:
            evidence.pop("candidate_payload", None)
        candidate.evidence_summary = evidence
        candidate.version += 1
        candidate.updated_at = utcnow()
        await session.flush()
        return candidate


def _set_or_remove(mapping: dict[str, object], key: str, value: object | None) -> None:
    if value in (None, ""):
        mapping.pop(key, None)
    else:
        mapping[key] = value


from .policy import utcnow  # noqa: E402
from .repository import EnrichmentWorkflowRepository  # noqa: E402
