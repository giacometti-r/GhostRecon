from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    ContactEnrichmentCreate,
    ContactEnrichmentOut,
    EmailCandidatePersistRequest,
    EmailCandidateRecordOut,
    EmailVerifyBatchRequest,
    EntityResolutionCreate,
    EntityResolutionOut,
    ReviewCandidateOut,
)
from ghostrecon.models.db import (
    Account,
    Contact,
    ContactEnrichmentCandidate,
    EmailCandidateRecord,
    EntityResolutionCase,
    OrganizationEmailPattern,
    OutboxEvent,
    ReviewCandidate,
)
from ghostrecon.services.email_candidates import generate_email_candidates
from ghostrecon.services.email_verifier import EmailVerifierClient

ENRICHMENT_SERVICE_NAME = "enrichment-service"
EMAIL_SERVICE_NAME = "email-intelligence-service"
REVIEW_SERVICE_NAME = "governance-service"
INCIDENT_CONTACT_ROLE_SCOPES = {"security", "it", "risk", "communications"}


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    cleaned = domain.lower().strip().removeprefix("https://").removeprefix("http://")
    return cleaned.split("/", 1)[0].strip(".") or None


def evaluate_contact_policy(payload: ContactEnrichmentCreate) -> tuple[str, str | None]:
    if payload.breached_data_source:
        return "blocked", "breached_data_rejected"
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
    limit: int = 100,
    settings: Settings | None = None,
) -> list[ContactEnrichmentCandidate]:
    async with session_scope(settings) as session:
        return await EnrichmentWorkflowRepository(session).list_contact_candidates(
            status=status, origin_type=origin_type, limit=limit
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
        stmt = select(EntityResolutionCase).order_by(EntityResolutionCase.created_at.desc()).limit(
            limit
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
        self, *, status: str | None, origin_type: str | None, limit: int
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
        result = await self.session.execute(stmt)
        return list(result.scalars())

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
            evidence_summary=evidence_summary,
            policy_snapshot=policy_snapshot,
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
