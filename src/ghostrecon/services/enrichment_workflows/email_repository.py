from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    EmailCandidatePersistRequest,
    EmailVerifyBatchRequest,
)
from ghostrecon.models.db import (
    Account,
    Contact,
    ContactEnrichmentCandidate,
    EmailCandidateRecord,
    OrganizationEmailPattern,
)
from ghostrecon.services.email_candidates import generate_email_candidates
from ghostrecon.services.email_verifier import EmailVerifierClient


class EmailRepositoryMixin:
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


from .policy import (  # noqa: E402
    EMAIL_SERVICE_NAME,
    classify_verification_result,
    normalize_domain,
    utcnow,
)
from .serializers import email_candidate_to_api  # noqa: E402
