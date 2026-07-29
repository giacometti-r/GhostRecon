from __future__ import annotations

from sqlalchemy import select

from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    ContactEnrichmentCreate,
)
from ghostrecon.models.db import (
    ContactEnrichmentCandidate,
    EntityResolutionCase,
    WatchTarget,
)
from ghostrecon.services.search_adapters import (
    SearchResult,
)
from ghostrecon.services.source_registry import (
    normalize_url,
)

from .policy import (  # noqa: E402
    ENRICHMENT_SERVICE_NAME,
    evaluate_contact_policy,
    normalize_domain,
)
from .serializers import (  # noqa: E402
    _contact_fields_from_result,
    _first_domain,
    _search_result_payload,
    contact_candidate_to_api,
)


class ContactRepositoryMixin:
    async def create_contact_candidate(
        self, payload: ContactEnrichmentCreate, idempotency_key: str
    ) -> ContactEnrichmentCandidate:
        existing = await self.session.scalar(
            select(ContactEnrichmentCandidate).where(
                ContactEnrichmentCandidate.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            return existing

        status, reason = evaluate_contact_policy(payload)
        account_id = payload.account_id
        resolution_case: EntityResolutionCase | None = None
        if payload.entity_resolution_case_id:
            resolution_case = await self.session.get(
                EntityResolutionCase, payload.entity_resolution_case_id
            )
            if resolution_case and resolution_case.status == "resolved":
                account_id = account_id or resolution_case.resolved_account_id
            elif status == "eligible":
                status = "needs_review"
                reason = "entity_resolution_unresolved"

        domain = normalize_domain(payload.domain)
        candidate = ContactEnrichmentCandidate(
            entity_resolution_case_id=payload.entity_resolution_case_id,
            account_id=account_id,
            origin_type=payload.origin_type,
            origin_id=payload.origin_id,
            published_name=payload.published_name,
            organization=payload.organization,
            title=payload.title,
            role_scope=payload.role_scope,
            domain=domain,
            profile_url=payload.profile_url,
            source_url=payload.source_url,
            status=status,
            eligibility_reason=reason,
            reuse_state=payload.reuse_state,
            source_definition_id=payload.source_definition_id,
            source_item_ids=list(payload.source_item_ids),
            policy_snapshot=payload.policy_snapshot,
            candidate_payload=payload.candidate_payload,
            review_reason=reason if status != "eligible" else None,
            idempotency_key=idempotency_key,
        )
        self.session.add(candidate)
        await self.session.flush()

        if candidate.status == "eligible":
            contact = await self._upsert_contact(candidate)
            candidate.contact_id = contact.id
            self._enqueue_event(
                new_event(
                    event_name=EventName.CONTACT_DISCOVERED,
                    aggregate_type="contact",
                    aggregate_id=contact.id,
                    source_service=ENRICHMENT_SERVICE_NAME,
                    source_definition_id=candidate.source_definition_id,
                    source_item_ids=[str(item) for item in candidate.source_item_ids],
                    payload={
                        "contact_id": contact.id,
                        "contact_enrichment_candidate_id": candidate.id,
                        "account_id": candidate.account_id,
                        "origin_type": candidate.origin_type,
                        "origin_id": candidate.origin_id,
                        "role_scope": candidate.role_scope,
                    },
                    idempotency_key=f"contact.discovered:{candidate.id}:{contact.id}",
                )
            )
        else:
            await self._request_review(
                candidate_type="contact_enrichment",
                target_type="contact_enrichment_candidate",
                target_id=candidate.id,
                origin_type=candidate.origin_type,
                origin_id=candidate.origin_id,
                source_definition_id=candidate.source_definition_id,
                source_item_ids=candidate.source_item_ids,
                reason_code=reason or "contact_enrichment_review_required",
                reason="Contact enrichment candidate requires analyst review.",
                evidence_summary=contact_candidate_to_api(candidate),
                policy_snapshot=candidate.policy_snapshot,
            )
        return candidate

    async def list_contact_candidates(
        self, *, status: str | None, origin_type: str | None, origin_id: str | None, limit: int
    ) -> list[ContactEnrichmentCandidate]:
        stmt = (
            select(ContactEnrichmentCandidate)
            .order_by(ContactEnrichmentCandidate.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(ContactEnrichmentCandidate.status == status)
        if origin_type:
            stmt = stmt.where(ContactEnrichmentCandidate.origin_type == origin_type)
        if origin_id:
            stmt = stmt.where(ContactEnrichmentCandidate.origin_id == origin_id)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def create_contact_candidates_from_search(
        self,
        target: WatchTarget,
        results: list[SearchResult],
        *,
        query: str,
        provider_name: str,
        actor: str,
    ) -> list[ContactEnrichmentCandidate]:
        candidates: list[ContactEnrichmentCandidate] = []
        source = await self._search_source_definition(provider_name, actor)
        for result in results:
            if not result.url:
                continue
            raw_item = await self._persist_search_raw_item(source, result, query=query)
            name, title, role_scope = _contact_fields_from_result(result)
            payload = ContactEnrichmentCreate(
                origin_type="security_incident" if target.origin_incident_id else "manual",
                origin_id=target.origin_incident_id or target.id,
                published_name=name,
                organization=target.display_name,
                title=title,
                role_scope=role_scope,
                domain=_first_domain(target.query_config),
                profile_url=result.url,
                source_url=result.url,
                source_definition_id=source.id,
                source_item_ids=[raw_item.id],
                policy_snapshot={
                    "source": provider_name,
                    "search_query": query,
                    "created_by": actor,
                },
                candidate_payload={
                    "search_result": _search_result_payload(result),
                    "watch_target_id": target.id,
                },
            )
            candidate = await self.create_contact_candidate(
                payload,
                f"watch-contact:{target.id}:{normalize_url(result.url)}",
            )
            candidates.append(candidate)
        if not candidates:
            target.monitoring_summary = {
                **(target.monitoring_summary or {}),
                "contact_discovery": {"query": query, "result_count": 0, "provider": provider_name},
            }
        return candidates
