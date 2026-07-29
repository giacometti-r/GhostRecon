from __future__ import annotations

from sqlalchemy import select

from ghostrecon.models.db import (
    ContactEnrichmentCandidate,
    RawSourceItem,
    SourceDefinition,
)
from ghostrecon.services.search_adapters import (
    SearchResult,
    is_suspicious_domain,
    registrable_domain_from_url,
)
from ghostrecon.services.source_registry import (
    build_raw_item_idempotency_key,
    content_hash,
    normalize_url,
    permitted_excerpt,
)

from .policy import (  # noqa: E402
    INCIDENT_CONTACT_ROLE_SCOPES,
    utcnow,
)
from .serializers import (  # noqa: E402
    _append_unique,
    _search_result_payload,
    contact_candidate_to_api,
)


class DomainDiscoveryRepositoryMixin:
    async def apply_domain_discovery(
        self,
        candidate: ContactEnrichmentCandidate,
        results: list[SearchResult],
        *,
        query: str,
        provider_name: str,
        actor: str,
    ) -> SearchResult | None:
        source = await self._search_source_definition(provider_name, actor)
        selected: SearchResult | None = None
        selected_domain: str | None = None
        for result in results:
            domain = registrable_domain_from_url(result.url)
            if is_suspicious_domain(domain):
                continue
            selected = result
            selected_domain = domain
            break

        evidence_result = selected or (results[0] if results else None)
        raw_item = (
            await self._persist_search_raw_item(source, evidence_result, query=query)
            if evidence_result
            else None
        )
        discovery_payload = {
            "query": query,
            "provider": provider_name,
            "actor": actor,
            "results": [_search_result_payload(result) for result in results],
            "selected_url": selected.url if selected else None,
            "selected_domain": selected_domain,
        }
        candidate.candidate_payload = {
            **(candidate.candidate_payload or {}),
            "domain_discovery": discovery_payload,
        }
        if selected_domain and raw_item is not None:
            candidate.domain = selected_domain
            candidate.source_definition_id = candidate.source_definition_id or source.id
            candidate.source_item_ids = _append_unique(candidate.source_item_ids, raw_item.id)
            if candidate.role_scope in INCIDENT_CONTACT_ROLE_SCOPES:
                candidate.status = "eligible"
                candidate.review_reason = None
                candidate.eligibility_reason = None
                if candidate.contact_id is None:
                    contact = await self._upsert_contact(candidate)
                    candidate.contact_id = contact.id
            else:
                candidate.status = "needs_review"
                candidate.review_reason = "domain_discovery_role_review_required"
                candidate.eligibility_reason = "domain_discovery_role_review_required"
        else:
            if raw_item is not None:
                candidate.source_definition_id = candidate.source_definition_id or source.id
                candidate.source_item_ids = _append_unique(candidate.source_item_ids, raw_item.id)
            candidate.status = "needs_review"
            candidate.review_reason = "domain_discovery_failed"
            candidate.eligibility_reason = "domain_discovery_failed"
            await self._request_review(
                candidate_type="contact_enrichment",
                target_type="contact_enrichment_candidate",
                target_id=candidate.id,
                origin_type=candidate.origin_type,
                origin_id=candidate.origin_id,
                source_definition_id=source.id,
                source_item_ids=[str(item) for item in candidate.source_item_ids or []],
                reason_code="domain_discovery_failed",
                reason="Company domain discovery returned no suitable official website.",
                evidence_summary=contact_candidate_to_api(candidate),
                policy_snapshot=candidate.policy_snapshot,
            )
        candidate.version += 1
        await self.session.flush()
        return selected

    async def _mark_candidate_for_review(
        self,
        candidate: ContactEnrichmentCandidate,
        *,
        actor: str,
        reason_code: str,
        reason: str,
    ) -> None:
        source = (
            await self.session.get(SourceDefinition, candidate.source_definition_id)
            if candidate.source_definition_id
            else await self._search_source_definition("manual_review", actor)
        )
        candidate.status = "needs_review"
        candidate.review_reason = reason_code
        candidate.eligibility_reason = reason_code
        candidate.version += 1
        await self._request_review(
            candidate_type="contact_enrichment",
            target_type="contact_enrichment_candidate",
            target_id=candidate.id,
            origin_type=candidate.origin_type,
            origin_id=candidate.origin_id,
            source_definition_id=source.id if source else None,
            source_item_ids=[str(item) for item in candidate.source_item_ids or []],
            reason_code=reason_code,
            reason=reason,
            evidence_summary=contact_candidate_to_api(candidate),
            policy_snapshot=candidate.policy_snapshot,
        )
        await self.session.flush()

    async def _search_source_definition(self, provider_name: str, actor: str) -> SourceDefinition:
        name = f"GhostRecon {provider_name} enrichment search"
        existing = await self.session.scalar(
            select(SourceDefinition).where(SourceDefinition.name == name)
        )
        now = utcnow()
        if existing is not None:
            return existing
        source = SourceDefinition(
            name=name,
            source_kind="enrichment",
            adapter_type=provider_name,
            base_url=provider_name,
            owner=actor,
            query_scope={"purpose": "contact_domain_discovery"},
            credentials_ref=None,
            rate_limit_policy={},
            polling_interval_seconds=None,
            freshness_slo_seconds=86400,
            checkpoint_strategy=None,
            checkpoint_state={},
            policy_state="allowed",
            policy_evidence={"local_policy": "public_search_results_only"},
            policy_reviewed_at=now,
            participant_reuse_state="allowed",
            participant_reuse_evidence={"reason": "public search result snippets"},
            content_storage_policy="metadata_excerpt",
            default_language="en",
            expected_timezone=None,
            enabled=True,
            operating_state="enabled",
            last_fetch_at=now,
            last_success_at=now,
            consecutive_failures=0,
        )
        self.session.add(source)
        await self.session.flush()
        return source

    async def _persist_search_raw_item(
        self, source: SourceDefinition, result: SearchResult, *, query: str
    ) -> RawSourceItem:
        canonical_url = normalize_url(result.url)
        body = "\n".join(part for part in (result.title, result.snippet) if part)
        item_hash = content_hash(body or canonical_url)
        idempotency_key = build_raw_item_idempotency_key(
            source.id,
            canonical_url,
            canonical_url,
            item_hash,
        )
        existing = await self.session.scalar(
            select(RawSourceItem).where(RawSourceItem.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
        raw_item = RawSourceItem(
            source_definition_id=source.id,
            external_id=None,
            original_url=result.url,
            canonical_url=canonical_url,
            content_hash=item_hash,
            retrieved_at=utcnow(),
            published_at=None,
            original_language="en",
            source_timezone=None,
            raw_metadata={
                "search_query": query,
                "search_result": _search_result_payload(result),
            },
            permitted_excerpt=permitted_excerpt(body, source.content_storage_policy),
            parse_status="parsed",
            duplicate_state="canonical",
            idempotency_key=idempotency_key,
        )
        self.session.add(raw_item)
        await self.session.flush()
        return raw_item
