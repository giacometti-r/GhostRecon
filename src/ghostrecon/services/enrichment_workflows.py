from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    ContactDomainDiscoveryResult,
    ContactEnrichmentCreate,
    ContactEnrichmentOut,
    EmailCandidatePersistRequest,
    EmailCandidateRecordOut,
    EmailVerifyBatchRequest,
    EntityResolutionCreate,
    EntityResolutionOut,
    EventParticipantEnrichRequest,
    EventParticipantEnrichResult,
    ReviewCandidateOut,
    ReviewCandidateUpdateRequest,
    WatchTargetContactDiscoveryResult,
    WatchTargetOut,
)
from ghostrecon.models.db import (
    Account,
    Contact,
    ContactEnrichmentCandidate,
    EmailCandidateRecord,
    EntityResolutionCase,
    EventParticipant,
    OrganizationEmailPattern,
    OutboxEvent,
    RawSourceItem,
    ReviewCandidate,
    SourceDefinition,
    WatchTarget,
)
from ghostrecon.services.email_candidates import generate_email_candidates
from ghostrecon.services.email_verifier import EmailVerifierClient
from ghostrecon.services.search_adapters import (
    SearchResult,
    is_suspicious_domain,
    linkedin_contact_query,
    official_website_query,
    registrable_domain_from_url,
    search_provider_for_settings,
)
from ghostrecon.services.source_registry import (
    build_raw_item_idempotency_key,
    content_hash,
    normalize_url,
    permitted_excerpt,
)

ENRICHMENT_SERVICE_NAME = "enrichment-service"
EMAIL_SERVICE_NAME = "email-intelligence-service"
REVIEW_SERVICE_NAME = "governance-service"
INCIDENT_CONTACT_ROLE_SCOPES = {"security", "it", "risk", "communications"}


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    resolved = registrable_domain_from_url(domain)
    if resolved:
        return resolved
    cleaned = domain.lower().strip().removeprefix("https://").removeprefix("http://")
    return cleaned.split("/", 1)[0].removeprefix("www.").strip(".") or None


def inferred_demo_domain(*values: str | None) -> str | None:
    for value in values:
        text = str(value or "").strip().lower()
        if not text:
            continue
        if "." in text and " " not in text:
            return normalize_domain(text)
        tokens = [
            token
            for token in "".join(char if char.isalnum() else " " for char in text).split()
            if token not in {"inc", "llc", "ltd", "corp", "corporation", "company", "demo"}
        ]
        if tokens:
            return f"{'-'.join(tokens[:3])}.com"
    return None


def _json_safe(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def evaluate_contact_policy(payload: ContactEnrichmentCreate) -> tuple[str, str | None]:
    if payload.breached_data_source:
        return "blocked", "breached_data_rejected"
    if payload.origin_type == "manual" and payload.candidate_payload.get("created_by"):
        return "eligible", None
    if not payload.source_definition_id or not payload.source_item_ids:
        return "blocked", "missing_source_lineage"
    if payload.origin_type == "event_participant" and payload.reuse_state != "allowed":
        return "blocked", "participant_reuse_not_allowed"
    if (
        payload.origin_type == "security_incident"
        and payload.role_scope not in INCIDENT_CONTACT_ROLE_SCOPES
    ):
        return "blocked", "incident_role_out_of_scope"
    return "eligible", None


def classify_verification_result(result: dict[str, object]) -> tuple[str, str | None]:
    status = str(result.get("status") or result.get("result") or "").lower()
    deliverability = str(result.get("deliverability") or "").lower()
    if result.get("error") or status in {"failed", "error", "timeout"}:
        return "failed", "verifier_failed"
    if _truthy(result, "catch_all", "catchall", "is_catch_all"):
        return "needs_review", "catch_all_domain"
    if _truthy(result, "ambiguous", "unknown", "risky"):
        return "needs_review", "ambiguous_verification"
    if _truthy(result, "role_based", "role_account", "disposable"):
        return "needs_review", "policy_review_required"
    if status in {"invalid", "undeliverable", "rejected"} or result.get("valid") is False:
        return "invalid", "invalid_email"
    if status in {"valid", "deliverable", "ok"} or deliverability in {"deliverable", "valid"}:
        return "verified", None
    if result.get("valid") is True:
        return "verified", None
    return "needs_review", "ambiguous_verification"


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
        if candidate.domain is None:
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
    async with session_scope(resolved) as session:
        participant = await session.get(EventParticipant, participant_id)
        if participant is None:
            raise ValueError("event participant not found")
        repository = EnrichmentWorkflowRepository(session)
        source_item_ids = [participant.source_item_id] if participant.source_item_id else []
        domain = normalize_domain(payload.domain) or inferred_demo_domain(
            participant.organization,
            participant.published_name,
        )
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
    async with session_scope(settings) as session:
        repository = EnrichmentWorkflowRepository(session)
        candidate = await session.get(ContactEnrichmentCandidate, candidate_id)
        if candidate is None:
            return None
        if not candidate.domain:
            inferred = inferred_demo_domain(candidate.organization, candidate.published_name)
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


class EnrichmentWorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_entity_resolution(
        self, payload: EntityResolutionCreate, idempotency_key: str
    ) -> EntityResolutionCase:
        existing = await self.session.scalar(
            select(EntityResolutionCase).where(
                EntityResolutionCase.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            return existing

        domain = normalize_domain(payload.domain)
        case = EntityResolutionCase(
            origin_type=payload.origin_type,
            origin_id=payload.origin_id,
            entity_kind=payload.entity_kind,
            input_name=payload.organization_name,
            input_domain=domain,
            source_definition_id=payload.source_definition_id,
            source_item_ids=list(payload.source_item_ids),
            policy_snapshot=payload.policy_snapshot,
            idempotency_key=idempotency_key,
        )
        self.session.add(case)
        await self.session.flush()

        if not payload.source_definition_id or not payload.source_item_ids:
            case.status = "blocked"
            case.review_reason = "missing_source_lineage"
            await self._request_review(
                candidate_type="entity_resolution",
                target_type="entity_resolution_case",
                target_id=case.id,
                origin_type=case.origin_type,
                origin_id=case.origin_id,
                source_definition_id=case.source_definition_id,
                source_item_ids=case.source_item_ids,
                reason_code="missing_source_lineage",
                reason="Entity resolution input did not include source lineage.",
                evidence_summary=entity_resolution_to_api(case),
                policy_snapshot=case.policy_snapshot,
            )
            return case

        matches = await self._find_account_matches(domain, payload.organization_name)
        case.alternatives = [_account_summary(account) for account in matches]
        if len(matches) == 1:
            account = matches[0]
            case.status = "resolved"
            case.confidence = 100 if domain else 90
            case.resolved_account_id = account.id
            case.resolved_name = account.company_name
            case.resolved_domain = account.domain
            self._enqueue_event(
                new_event(
                    event_name=EventName.ACCOUNT_ENRICHED,
                    aggregate_type="account",
                    aggregate_id=account.id,
                    source_service=ENRICHMENT_SERVICE_NAME,
                    source_definition_id=case.source_definition_id,
                    source_item_ids=[str(item) for item in case.source_item_ids],
                    payload={
                        "account_id": account.id,
                        "domain": account.domain,
                        "origin_type": case.origin_type,
                        "origin_id": case.origin_id,
                        "resolution_case_id": case.id,
                    },
                    idempotency_key=f"account.enriched:{case.id}:{account.id}",
                )
            )
        else:
            case.status = "ambiguous" if len(matches) > 1 else "needs_review"
            case.confidence = 60 if matches else 0
            case.review_reason = "multiple_account_matches" if matches else "no_account_match"
            await self._request_review(
                candidate_type="entity_resolution",
                target_type="entity_resolution_case",
                target_id=case.id,
                origin_type=case.origin_type,
                origin_id=case.origin_id,
                source_definition_id=case.source_definition_id,
                source_item_ids=case.source_item_ids,
                reason_code=case.review_reason,
                reason="Entity resolution requires analyst review.",
                evidence_summary=entity_resolution_to_api(case),
                policy_snapshot=case.policy_snapshot,
            )
        return case

    async def list_entity_resolutions(
        self, *, status: str | None, origin_type: str | None, limit: int
    ) -> list[EntityResolutionCase]:
        stmt = (
            select(EntityResolutionCase)
            .order_by(EntityResolutionCase.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(EntityResolutionCase.status == status)
        if origin_type:
            stmt = stmt.where(EntityResolutionCase.origin_type == origin_type)
        result = await self.session.execute(stmt)
        return list(result.scalars())

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
            else await self._search_source_definition("local_demo", actor)
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

    async def persist_email_candidates(
        self, payload: EmailCandidatePersistRequest, idempotency_key: str
    ) -> list[EmailCandidateRecord]:
        contact, lineage = await self._resolve_email_contact_context(payload)
        if not lineage["source_definition_id"] or not lineage["source_item_ids"]:
            raise ValueError("email candidate persistence requires source lineage")

        full_name = payload.full_name or contact.full_name
        patterns = await self._email_patterns(payload.domain, payload.known_patterns)
        generated = generate_email_candidates(full_name, payload.domain, patterns)
        records: list[EmailCandidateRecord] = []
        for generated_candidate in generated:
            candidate_key = f"{idempotency_key}:{contact.id}:{generated_candidate.email}"
            existing = await self.session.scalar(
                select(EmailCandidateRecord).where(
                    EmailCandidateRecord.idempotency_key == candidate_key
                )
            )
            if existing is not None:
                records.append(existing)
                continue
            record = EmailCandidateRecord(
                contact_id=contact.id,
                email=str(generated_candidate.email),
                pattern=generated_candidate.pattern,
                verification_status="pending",
                source_definition_id=lineage["source_definition_id"],
                source_item_ids=lineage["source_item_ids"],
                origin_type=lineage["origin_type"],
                origin_id=lineage["origin_id"],
                policy_snapshot=lineage["policy_snapshot"],
                idempotency_key=candidate_key,
            )
            self.session.add(record)
            await self.session.flush()
            self._enqueue_event(
                new_event(
                    event_name=EventName.EMAIL_CANDIDATE_GENERATED,
                    aggregate_type="email_candidate",
                    aggregate_id=record.id,
                    source_service=EMAIL_SERVICE_NAME,
                    source_definition_id=record.source_definition_id,
                    source_item_ids=[str(item) for item in record.source_item_ids],
                    payload={
                        "email_candidate_id": record.id,
                        "contact_id": contact.id,
                        "email": record.email,
                        "pattern": record.pattern,
                    },
                    idempotency_key=f"email.candidate_generated:{record.id}",
                )
            )
            records.append(record)
        return records

    async def verify_email_candidates(
        self, payload: EmailVerifyBatchRequest, verifier: EmailVerifierClient
    ) -> list[EmailCandidateRecord]:
        if not payload.candidate_ids:
            return []
        result = await self.session.execute(
            select(EmailCandidateRecord).where(EmailCandidateRecord.id.in_(payload.candidate_ids))
        )
        records = list(result.scalars())
        verification_results = dict(payload.verification_results)
        if not verification_results:
            verification_results = await self._fetch_verification_results(records, verifier)

        for record in records:
            raw_result = verification_results.get(record.id) or verification_results.get(
                record.email
            )
            if raw_result is None:
                raw_result = {"error": "missing_verification_result"}
            status, reason = classify_verification_result(raw_result)
            record.verification_status = status
            record.verification_payload = raw_result
            record.verification_checked_at = utcnow()
            record.version += 1
            if status == "verified":
                record.review_status = "not_required"
                record.review_reason = None
                if record.contact_id:
                    contact = await self.session.get(Contact, record.contact_id)
                    if contact is not None:
                        contact.email = record.email
                        contact.email_status = "verified"
                        contact.updated_at = utcnow()
                await self._upsert_email_pattern(record)
                self._enqueue_event(
                    new_event(
                        event_name=EventName.EMAIL_VERIFIED,
                        aggregate_type="email_candidate",
                        aggregate_id=record.id,
                        source_service=EMAIL_SERVICE_NAME,
                        source_definition_id=record.source_definition_id,
                        source_item_ids=[str(item) for item in record.source_item_ids],
                        payload={
                            "email_candidate_id": record.id,
                            "email": record.email,
                            "verification_status": record.verification_status,
                        },
                        idempotency_key=f"email.verified:{record.id}:{record.version}",
                    )
                )
            elif status in {"needs_review", "failed"}:
                record.review_status = "needs_review"
                record.review_reason = reason
                await self._request_review(
                    candidate_type="email_verification",
                    target_type="email_candidate",
                    target_id=record.id,
                    origin_type=record.origin_type,
                    origin_id=record.origin_id,
                    source_definition_id=record.source_definition_id,
                    source_item_ids=record.source_item_ids,
                    reason_code=reason or "email_verification_review_required",
                    reason="Email verification result requires analyst review.",
                    evidence_summary=email_candidate_to_api(record),
                    policy_snapshot=record.policy_snapshot,
                )
        return records

    async def list_review_candidates(
        self, *, status: str | None, candidate_type: str | None, limit: int
    ) -> list[ReviewCandidate]:
        stmt = select(ReviewCandidate).order_by(ReviewCandidate.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(ReviewCandidate.status == status)
        if candidate_type:
            stmt = stmt.where(ReviewCandidate.candidate_type == candidate_type)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def _find_account_matches(
        self, domain: str | None, organization_name: str | None
    ) -> list[Account]:
        if domain:
            result = await self.session.execute(
                select(Account).where(func.lower(Account.domain) == domain.lower()).limit(10)
            )
            matches = list(result.scalars())
            if matches:
                return matches
        if organization_name:
            result = await self.session.execute(
                select(Account)
                .where(func.lower(Account.company_name) == organization_name.lower())
                .limit(10)
            )
            return list(result.scalars())
        return []

    async def _upsert_contact(self, candidate: ContactEnrichmentCandidate) -> Contact:
        contact_key = f"contact:{candidate.idempotency_key}"
        existing = await self.session.scalar(
            select(Contact).where(Contact.idempotency_key == contact_key)
        )
        if existing is not None:
            return existing
        contact = Contact(
            account_id=candidate.account_id,
            full_name=candidate.published_name,
            title=candidate.title,
            email=None,
            source_vendor="public_enrichment",
            source_confidence=80,
            source_url=candidate.source_url,
            source_definition_id=candidate.source_definition_id,
            source_item_ids=candidate.source_item_ids,
            origin_type=candidate.origin_type,
            origin_id=candidate.origin_id,
            source_policy_snapshot=candidate.policy_snapshot,
            idempotency_key=contact_key,
        )
        self.session.add(contact)
        await self.session.flush()
        return contact

    async def _resolve_email_contact_context(
        self, payload: EmailCandidatePersistRequest
    ) -> tuple[Contact, dict[str, Any]]:
        candidate: ContactEnrichmentCandidate | None = None
        if payload.contact_candidate_id:
            candidate = await self.session.get(
                ContactEnrichmentCandidate, payload.contact_candidate_id
            )
            if candidate is None:
                raise ValueError("contact candidate not found")
            if candidate.status != "eligible" or not candidate.contact_id:
                raise ValueError("contact candidate is not eligible for email generation")
            contact = await self.session.get(Contact, candidate.contact_id)
            if contact is None:
                raise ValueError("contact not found for candidate")
            return contact, {
                "origin_type": candidate.origin_type,
                "origin_id": candidate.origin_id,
                "source_definition_id": candidate.source_definition_id,
                "source_item_ids": candidate.source_item_ids,
                "policy_snapshot": candidate.policy_snapshot,
            }
        if not payload.contact_id:
            raise ValueError("contact_id or contact_candidate_id is required")
        contact = await self.session.get(Contact, payload.contact_id)
        if contact is None:
            raise ValueError("contact not found")
        return contact, {
            "origin_type": payload.origin_type or contact.origin_type,
            "origin_id": payload.origin_id or contact.origin_id,
            "source_definition_id": payload.source_definition_id or contact.source_definition_id,
            "source_item_ids": payload.source_item_ids or contact.source_item_ids,
            "policy_snapshot": payload.policy_snapshot or contact.source_policy_snapshot,
        }

    async def _email_patterns(self, domain: str, requested: list[str]) -> list[str] | None:
        normalized = normalize_domain(domain)
        if not normalized:
            return requested or None
        result = await self.session.execute(
            select(OrganizationEmailPattern)
            .where(OrganizationEmailPattern.domain == normalized)
            .order_by(OrganizationEmailPattern.confidence.desc())
            .limit(5)
        )
        learned = [pattern.pattern for pattern in result.scalars()]
        patterns = [*requested, *learned]
        deduped = list(dict.fromkeys(patterns))
        return deduped or None

    async def _fetch_verification_results(
        self, records: list[EmailCandidateRecord], verifier: EmailVerifierClient
    ) -> dict[str, dict[str, object]]:
        response = await verifier.validate_batch([record.email for record in records])
        if isinstance(response.get("results"), list):
            return {
                str(item.get("email")): item
                for item in response["results"]
                if isinstance(item, dict) and item.get("email")
            }
        if isinstance(response.get("results"), dict):
            return response["results"]  # type: ignore[return-value]
        return {
            record.email: response.get(record.email, {})  # type: ignore[index]
            for record in records
            if isinstance(response.get(record.email), dict)
        }

    async def _upsert_email_pattern(self, record: EmailCandidateRecord) -> None:
        domain = record.email.rsplit("@", 1)[-1].lower()
        existing = await self.session.scalar(
            select(OrganizationEmailPattern).where(
                OrganizationEmailPattern.domain == domain,
                OrganizationEmailPattern.pattern == record.pattern,
            )
        )
        if existing is not None:
            existing.sample_size += 1
            existing.confidence = max(existing.confidence, 100)
            existing.verified_at = record.verification_checked_at
            return
        self.session.add(
            OrganizationEmailPattern(
                domain=domain,
                pattern=record.pattern,
                confidence=100,
                verified_at=record.verification_checked_at,
                idempotency_key=f"email-pattern:{domain}:{record.pattern}",
            )
        )

    async def _request_review(
        self,
        *,
        candidate_type: str,
        target_type: str,
        target_id: str,
        origin_type: str | None,
        origin_id: str | None,
        source_definition_id: str | None,
        source_item_ids: list[object],
        reason_code: str,
        reason: str,
        evidence_summary: dict[str, object],
        policy_snapshot: dict[str, object],
    ) -> ReviewCandidate:
        idempotency_key = f"review:{candidate_type}:{target_id}:{reason_code}"
        existing = await self.session.scalar(
            select(ReviewCandidate).where(ReviewCandidate.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
        review = ReviewCandidate(
            candidate_type=candidate_type,
            target_type=target_type,
            target_id=target_id,
            origin_type=origin_type,
            origin_id=origin_id,
            source_definition_id=source_definition_id,
            source_item_ids=source_item_ids,
            reason_code=reason_code,
            reason=reason,
            evidence_summary=_json_safe(evidence_summary),
            policy_snapshot=_json_safe(policy_snapshot),
            idempotency_key=idempotency_key,
        )
        self.session.add(review)
        await self.session.flush()
        self._enqueue_event(
            new_event(
                event_name=EventName.APPROVAL_REQUESTED,
                aggregate_type="review_candidate",
                aggregate_id=review.id,
                source_service=REVIEW_SERVICE_NAME,
                source_definition_id=source_definition_id,
                source_item_ids=[str(item) for item in source_item_ids],
                payload={
                    "review_candidate_id": review.id,
                    "candidate_type": review.candidate_type,
                    "target_type": review.target_type,
                    "target_id": review.target_id,
                    "reason_code": review.reason_code,
                },
                idempotency_key=f"approval.requested:{review.id}",
            )
        )
        return review

    def _enqueue_event(self, event: Any) -> OutboxEvent:
        payload = event.model_dump(mode="json")
        outbox_event = OutboxEvent(
            event_name=payload["event_name"],
            aggregate_type=payload["aggregate_type"],
            aggregate_id=payload["aggregate_id"],
            idempotency_key=payload["idempotency_key"],
            payload=payload,
        )
        self.session.add(outbox_event)
        return outbox_event


def entity_resolution_to_api(case: EntityResolutionCase) -> dict[str, object]:
    return {
        "id": case.id,
        "origin_type": case.origin_type,
        "origin_id": case.origin_id,
        "entity_kind": case.entity_kind,
        "input_name": case.input_name,
        "input_domain": case.input_domain,
        "resolved_account_id": case.resolved_account_id,
        "resolved_name": case.resolved_name,
        "resolved_domain": case.resolved_domain,
        "status": case.status,
        "confidence": case.confidence,
        "alternatives": case.alternatives or [],
        "source_definition_id": case.source_definition_id,
        "source_item_ids": case.source_item_ids or [],
        "policy_snapshot": case.policy_snapshot or {},
        "review_reason": case.review_reason,
        "version": case.version,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
    }


def _watch_target_api(target: WatchTarget) -> dict[str, object]:
    return {
        "id": target.id,
        "target_type": target.target_type,
        "canonical_target_key": target.canonical_target_key,
        "display_name": target.display_name,
        "query_config": target.query_config or {},
        "enabled": target.enabled,
        "monitoring_enabled": target.enabled,
        "monitoring_status": target.monitoring_status,
        "last_monitored_at": target.last_monitored_at,
        "next_monitoring_at": target.next_monitoring_at,
        "monitoring_error": target.monitoring_error,
        "monitoring_summary": target.monitoring_summary or {},
        "owner": target.owner,
        "origin_incident_id": target.origin_incident_id,
        "created_by": target.created_by,
        "version": target.version,
        "created_at": target.created_at,
        "updated_at": target.updated_at,
    }


def _contact_fields_from_result(result: SearchResult) -> tuple[str, str | None, str]:
    title = result.title.replace(" | LinkedIn", "").replace(" - LinkedIn", "").strip()
    name = title.split("|", 1)[0].split("-", 1)[0].strip() or "Unknown Contact"
    text = f"{result.title} {result.snippet or ''}".lower()
    if "ciso" in text or "cybersecurity" in text or "information security" in text:
        role_scope = "security"
        job_title = "CISO" if "ciso" in text else "Head of Cybersecurity"
    elif "cio" in text:
        role_scope = "it"
        job_title = "CIO"
    elif "cto" in text:
        role_scope = "it"
        job_title = "CTO"
    else:
        role_scope = "unknown"
        job_title = None
    return name, job_title, role_scope


def _first_domain(query_config: dict[str, object] | None) -> str | None:
    domains = (query_config or {}).get("domains")
    if isinstance(domains, list) and domains:
        return normalize_domain(str(domains[0]))
    return None


def _search_result_payload(result: SearchResult) -> dict[str, object]:
    return {
        "title": result.title,
        "url": result.url,
        "snippet": result.snippet,
        "rank": result.rank,
        "source": result.source,
        "published_at": result.published_at,
        "raw": result.raw or {},
    }


def _append_unique(values: list[object] | None, value: object) -> list[object]:
    resolved = list(values or [])
    if value not in resolved:
        resolved.append(value)
    return resolved


def contact_candidate_to_api(candidate: ContactEnrichmentCandidate) -> dict[str, object]:
    return {
        "id": candidate.id,
        "entity_resolution_case_id": candidate.entity_resolution_case_id,
        "account_id": candidate.account_id,
        "contact_id": candidate.contact_id,
        "origin_type": candidate.origin_type,
        "origin_id": candidate.origin_id,
        "published_name": candidate.published_name,
        "organization": candidate.organization,
        "title": candidate.title,
        "role_scope": candidate.role_scope,
        "domain": candidate.domain,
        "profile_url": candidate.profile_url,
        "source_url": candidate.source_url,
        "status": candidate.status,
        "eligibility_reason": candidate.eligibility_reason,
        "reuse_state": candidate.reuse_state,
        "source_definition_id": candidate.source_definition_id,
        "source_item_ids": candidate.source_item_ids or [],
        "policy_snapshot": candidate.policy_snapshot or {},
        "candidate_payload": candidate.candidate_payload or {},
        "review_reason": candidate.review_reason,
        "version": candidate.version,
        "created_at": candidate.created_at,
        "updated_at": candidate.updated_at,
    }


def email_candidate_to_api(candidate: EmailCandidateRecord) -> dict[str, object]:
    return {
        "id": candidate.id,
        "contact_id": candidate.contact_id,
        "email": candidate.email,
        "pattern": candidate.pattern,
        "verification_status": candidate.verification_status,
        "verification_payload": candidate.verification_payload or {},
        "verification_checked_at": candidate.verification_checked_at,
        "source_definition_id": candidate.source_definition_id,
        "source_item_ids": candidate.source_item_ids or [],
        "origin_type": candidate.origin_type,
        "origin_id": candidate.origin_id,
        "policy_snapshot": candidate.policy_snapshot or {},
        "review_status": candidate.review_status,
        "review_reason": candidate.review_reason,
        "version": candidate.version,
        "created_at": candidate.created_at,
    }


def review_candidate_to_api(candidate: ReviewCandidate) -> dict[str, object]:
    return {
        "id": candidate.id,
        "candidate_type": candidate.candidate_type,
        "target_type": candidate.target_type,
        "target_id": candidate.target_id,
        "origin_type": candidate.origin_type,
        "origin_id": candidate.origin_id,
        "source_definition_id": candidate.source_definition_id,
        "source_item_ids": candidate.source_item_ids or [],
        "status": candidate.status,
        "reason_code": candidate.reason_code,
        "reason": candidate.reason,
        "evidence_summary": candidate.evidence_summary or {},
        "policy_snapshot": candidate.policy_snapshot or {},
        "policy_snapshot_hash": getattr(candidate, "policy_snapshot_hash", None),
        "sla_due_at": getattr(candidate, "sla_due_at", None),
        "version": candidate.version,
        "created_at": candidate.created_at,
        "updated_at": candidate.updated_at,
    }


def entity_resolution_to_model(case: EntityResolutionCase) -> EntityResolutionOut:
    return EntityResolutionOut.model_validate(entity_resolution_to_api(case))


def contact_candidate_to_model(candidate: ContactEnrichmentCandidate) -> ContactEnrichmentOut:
    return ContactEnrichmentOut.model_validate(contact_candidate_to_api(candidate))


def email_candidate_to_model(candidate: EmailCandidateRecord) -> EmailCandidateRecordOut:
    return EmailCandidateRecordOut.model_validate(email_candidate_to_api(candidate))


def review_candidate_to_model(candidate: ReviewCandidate) -> ReviewCandidateOut:
    return ReviewCandidateOut.model_validate(review_candidate_to_api(candidate))


def _truthy(result: dict[str, object], *keys: str) -> bool:
    return any(bool(result.get(key)) for key in keys)


def _account_summary(account: Account) -> dict[str, object]:
    return {
        "account_id": account.id,
        "domain": account.domain,
        "company_name": account.company_name,
    }
