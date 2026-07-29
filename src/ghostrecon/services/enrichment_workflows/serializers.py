from __future__ import annotations

from ghostrecon.models.api import (
    ContactEnrichmentOut,
    EmailCandidateRecordOut,
    EntityResolutionOut,
    ReviewCandidateOut,
)
from ghostrecon.models.db import (
    Account,
    ContactEnrichmentCandidate,
    EmailCandidateRecord,
    EntityResolutionCase,
    ReviewCandidate,
    WatchTarget,
)
from ghostrecon.services.search_adapters import (
    SearchResult,
)


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


from .policy import normalize_domain  # noqa: E402
