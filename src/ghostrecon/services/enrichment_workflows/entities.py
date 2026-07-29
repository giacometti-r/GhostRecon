from __future__ import annotations

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    ContactEnrichmentCreate,
    EntityResolutionCreate,
    WatchTargetContactDiscoveryResult,
    WatchTargetOut,
)
from ghostrecon.models.db import (
    ContactEnrichmentCandidate,
    EntityResolutionCase,
    WatchTarget,
)
from ghostrecon.services.search_adapters import (
    linkedin_contact_query,
    search_provider_for_settings,
)


async def create_entity_resolution(
    payload: EntityResolutionCreate,
    *,
    idempotency_key: str,
    settings: Settings | None = None,
) -> EntityResolutionCase:
    async with session_scope(settings) as session:
        return await EnrichmentWorkflowRepository(session).create_entity_resolution(
            payload, idempotency_key
        )


async def list_entity_resolutions(
    *,
    status: str | None = None,
    origin_type: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> list[EntityResolutionCase]:
    async with session_scope(settings) as session:
        return await EnrichmentWorkflowRepository(session).list_entity_resolutions(
            status=status, origin_type=origin_type, limit=limit
        )


async def create_contact_enrichment_candidate(
    payload: ContactEnrichmentCreate,
    *,
    idempotency_key: str,
    settings: Settings | None = None,
) -> ContactEnrichmentCandidate:
    async with session_scope(settings) as session:
        return await EnrichmentWorkflowRepository(session).create_contact_candidate(
            payload, idempotency_key
        )


async def list_contact_enrichment_candidates(
    *,
    status: str | None = None,
    origin_type: str | None = None,
    origin_id: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> list[ContactEnrichmentCandidate]:
    async with session_scope(settings) as session:
        return await EnrichmentWorkflowRepository(session).list_contact_candidates(
            status=status, origin_type=origin_type, origin_id=origin_id, limit=limit
        )


async def discover_watch_target_contacts(
    watch_target_id: str,
    *,
    actor: str,
    settings: Settings | None = None,
) -> WatchTargetContactDiscoveryResult | None:
    resolved = settings or Settings()
    provider = search_provider_for_settings(resolved)
    async with session_scope(resolved) as session:
        repository = EnrichmentWorkflowRepository(session)
        target = await session.get(WatchTarget, watch_target_id)
        if target is None:
            return None
        query = linkedin_contact_query(target.display_name)
        results = await provider.search(query, limit=resolved.search_result_limit)
        candidates = await repository.create_contact_candidates_from_search(
            target,
            results,
            query=query,
            provider_name=provider.provider_name,
            actor=actor,
        )
        return WatchTargetContactDiscoveryResult(
            watch_target=WatchTargetOut.model_validate(_watch_target_api(target)),
            query=query,
            provider=provider.provider_name,
            degraded=provider.provider_name == "disabled",
            contact_candidates=[contact_candidate_to_model(candidate) for candidate in candidates],
        )


from .repository import EnrichmentWorkflowRepository  # noqa: E402
from .serializers import _watch_target_api, contact_candidate_to_model  # noqa: E402
