from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.models.db import (
    Account,
    Contact,
    ContactEnrichmentCandidate,
    CrmExportBatch,
    CrmExportItem,
    CrmTarget,
    EmailCandidateRecord,
    ReviewCandidate,
    SecurityIncident,
    SourceDefinition,
)

from .ids import DEMO_SEED_IDS
from .persistence import _get_or_create, _selection_hash


async def _review_candidate(
    session: AsyncSession,
    record_id: str,
    *,
    now: datetime,
    target_type: str,
    target_id: str,
    origin_type: str,
    origin_id: str,
    source_definition_id: str,
    reason_code: str,
    reason: str,
    evidence_summary: dict[str, object],
    idempotency_key: str,
    sla_due_at: datetime,
    candidate_type: str = "incident_corroboration",
) -> ReviewCandidate:
    review = await _get_or_create(session, ReviewCandidate, record_id)
    review.candidate_type = candidate_type
    review.target_type = target_type
    review.target_id = target_id
    review.origin_type = origin_type
    review.origin_id = origin_id
    review.source_definition_id = source_definition_id
    review.source_item_ids = [f"{idempotency_key}:source-item"]
    review.status = "open"
    review.reason_code = reason_code
    review.reason = reason
    review.evidence_summary = evidence_summary
    review.policy_snapshot = {
        "lawful_basis": "synthetic_demo",
        "source_policy": "allowed",
        "incident_status": "corroborated",
        "corroboration_method": "analyst_decision",
        "suppression_allowed": True,
        "retention_state": "current",
    }
    review.policy_snapshot_hash = "demo-sprint15-policy-snapshot"
    review.sla_due_at = sla_due_at
    review.idempotency_key = idempotency_key
    review.version = 1
    review.created_at = now
    review.updated_at = now
    return review


async def _crm_target(
    session: AsyncSession,
    record_id: str,
    *,
    now: datetime,
    review_candidate_id: str,
    target_type: str,
    target_id: str,
    origin_id: str,
    source_definition_id: str,
    status: str,
    export_status: str,
    idempotency_key: str,
) -> CrmTarget:
    target = await _get_or_create(session, CrmTarget, record_id)
    target.review_candidate_id = review_candidate_id
    target.review_decision_id = None
    target.target_type = target_type
    target.target_id = target_id
    target.origin_type = "security_incident"
    target.origin_id = origin_id
    target.source_definition_id = source_definition_id
    target.source_item_ids = []
    target.status = status
    target.export_status = export_status
    target.policy_snapshot = {"lawful_basis": "synthetic_demo", "source_policy": "allowed"}
    target.approval_snapshot = {"approved_by": "demo-seed", "sprint": 15}
    target.idempotency_key = idempotency_key
    target.version = 1
    target.created_at = now
    target.updated_at = now
    return target


async def _crm_export_batch(
    session: AsyncSession,
    *,
    now: datetime,
    target: CrmTarget,
) -> None:
    batch = await _get_or_create(session, CrmExportBatch, DEMO_SEED_IDS.crm_export_batch_id)
    batch.provider = "attio"
    batch.workspace_id = "demo-workspace"
    batch.requested_by = "demo-analyst"
    batch.status = "partial"
    batch.crm_target_ids = [target.id]
    batch.selection_hash = _selection_hash([target.id])
    batch.idempotency_key = "demo:sprint15:crm-export-batch:retryable"
    batch.counts = {"total": 1, "failed_retryable": 1, "succeeded": 0}
    batch.reconciliation_summary = {"pending_reconciliation": 0}
    batch.started_at = now - timedelta(hours=2)
    batch.completed_at = now - timedelta(hours=1)
    batch.created_at = now - timedelta(hours=2)
    batch.updated_at = now - timedelta(hours=1)
    await session.flush()

    item = await _get_or_create(session, CrmExportItem, DEMO_SEED_IDS.crm_export_item_id)
    item.batch_id = batch.id
    item.crm_target_id = target.id
    item.target_type = target.target_type
    item.target_id = target.target_id
    item.operation = "upsert_record"
    item.dependency_item_ids = []
    item.provider_object = "people"
    item.provider_record_id = None
    item.provider_list_id = None
    item.provider_list_entry_id = None
    item.stable_match_key = f"ghostrecon_contact:{target.target_id}"
    item.status = "failed_retryable"
    item.attempt_count = 1
    item.last_error = "Synthetic Attio rate limit for retry demo."
    item.retry_after_seconds = 60
    item.reconciliation_state = "not_required"
    item.created_at = now - timedelta(hours=2)
    item.updated_at = now - timedelta(hours=1)


async def _seed_crm(
    session: AsyncSession,
    now: datetime,
    fresh_source: SourceDefinition,
    degraded_source: SourceDefinition,
    incident: SecurityIncident,
    review_incident: SecurityIncident,
    account: Account,
    contact: Contact,
    contact_candidate: ContactEnrichmentCandidate,
    domain_review_candidate: ContactEnrichmentCandidate,
    email_candidate: EmailCandidateRecord,
):
    await session.flush()

    approve_review = await _review_candidate(
        session,
        DEMO_SEED_IDS.approve_review_candidate_id,
        now=now,
        target_type="security_incident",
        target_id=incident.id,
        origin_type="security_incident",
        origin_id=incident.id,
        source_definition_id=degraded_source.id,
        reason_code="demo_incident_ready",
        reason="Synthetic candidate ready for approval during the local demo.",
        evidence_summary={
            "incident_title": incident.title,
            "affected_company": "Example Industries",
            "recommended_action": "approve for CRM export",
        },
        idempotency_key="demo:sprint15:review:approve-example-industries",
        sla_due_at=now + timedelta(days=2),
    )
    reject_review = await _review_candidate(
        session,
        DEMO_SEED_IDS.reject_review_candidate_id,
        now=now,
        target_type="security_incident",
        target_id=review_incident.id,
        origin_type="security_incident",
        origin_id=review_incident.id,
        source_definition_id=degraded_source.id,
        reason_code="demo_low_confidence",
        reason="Synthetic low-confidence candidate for rejection during the local demo.",
        evidence_summary={
            "incident_title": review_incident.title,
            "affected_company": "Nimbus Retail",
            "recommended_action": "reject as insufficient evidence",
        },
        idempotency_key="demo:sprint15:review:reject-nimbus-retail",
        sla_due_at=now + timedelta(days=1),
    )
    approve_review.status = "superseded"
    reject_review.status = "superseded"
    await _review_candidate(
        session,
        DEMO_SEED_IDS.contact_review_candidate_id,
        now=now,
        candidate_type="contact_enrichment",
        target_type="contact_enrichment_candidate",
        target_id=domain_review_candidate.id,
        origin_type="security_incident",
        origin_id=incident.id,
        source_definition_id=degraded_source.id,
        reason_code="domain_discovery_failed",
        reason="Official website discovery needs analyst review before accepting the contact.",
        evidence_summary={
            "company": "Example Industries",
            "published_name": domain_review_candidate.published_name,
            "title": domain_review_candidate.title,
            "profile_url": domain_review_candidate.profile_url,
        },
        idempotency_key="demo:sprint20:review:domain-discovery",
        sla_due_at=now + timedelta(days=1),
    )
    await _review_candidate(
        session,
        DEMO_SEED_IDS.email_review_candidate_id,
        now=now,
        candidate_type="email_verification",
        target_type="email_candidate",
        target_id=email_candidate.id,
        origin_type="security_incident",
        origin_id=incident.id,
        source_definition_id=degraded_source.id,
        reason_code="catch_all_domain",
        reason="The domain accepts mail broadly, so the generated email needs analyst review.",
        evidence_summary={
            "email": email_candidate.email,
            "contact": contact_candidate.published_name,
            "domain": "example-industries.test",
        },
        idempotency_key="demo:sprint20:review:email-verification",
        sla_due_at=now + timedelta(days=2),
    )
    await session.flush()

    export_target = await _crm_target(
        session,
        DEMO_SEED_IDS.export_crm_target_id,
        now=now,
        review_candidate_id=DEMO_SEED_IDS.email_review_candidate_id,
        target_type="email_candidate",
        target_id=email_candidate.id,
        origin_id=incident.id,
        source_definition_id=degraded_source.id,
        status="pending_export",
        export_status="not_exported",
        idempotency_key="demo:sprint15:crm-target:export-example-industries",
    )
    export_target.policy_snapshot = {
        **dict(export_target.policy_snapshot or {}),
        "name": contact.full_name,
        "company": account.company_name,
        "email": email_candidate.email,
    }
    export_target.approval_snapshot = {
        **dict(export_target.approval_snapshot or {}),
        "name": contact.full_name,
        "company": account.company_name,
        "email": email_candidate.email,
    }
    retry_target = await _crm_target(
        session,
        DEMO_SEED_IDS.retry_crm_target_id,
        now=now,
        review_candidate_id=DEMO_SEED_IDS.email_review_candidate_id,
        target_type="email_candidate",
        target_id=email_candidate.id,
        origin_id=review_incident.id,
        source_definition_id=degraded_source.id,
        status="pending_export",
        export_status="failed_retryable",
        idempotency_key="demo:sprint15:crm-target:retry-nimbus-retail",
    )
    retry_target.policy_snapshot = {
        **dict(retry_target.policy_snapshot or {}),
        "name": contact.full_name,
        "company": account.company_name,
        "email": email_candidate.email,
    }
    retry_target.approval_snapshot = {
        **dict(retry_target.approval_snapshot or {}),
        "name": contact.full_name,
        "company": account.company_name,
        "email": email_candidate.email,
    }
    meeting_target = await _crm_target(
        session,
        DEMO_SEED_IDS.meeting_crm_target_id,
        now=now,
        review_candidate_id=approve_review.id,
        target_type="contact",
        target_id=contact.id,
        origin_id=incident.id,
        source_definition_id=fresh_source.id,
        status="exported",
        export_status="exported",
        idempotency_key="demo:sprint15:crm-target:meeting-taylor-ng",
    )
    await session.flush()
    return export_target, retry_target, meeting_target
