from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.db import (
    Account,
    Contact,
    CrmExportBatch,
    CrmExportItem,
    CrmTarget,
    CyberEvent,
    EventParticipant,
    MeetingFollowUpTask,
    MeetingHandoff,
    MeetingPrepPacket,
    ReviewCandidate,
    SecurityIncident,
    Sequence,
    SequenceEnrollment,
    SequenceStep,
    SourceDefinition,
    WatchTarget,
)

DEMO_NAMESPACE = "https://ghostrecon.local/demo/sprint-15"


def _seed_uuid(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{DEMO_NAMESPACE}/{name}"))


@dataclass(frozen=True)
class DemoSeedIds:
    fresh_source_definition_id: str = _seed_uuid("source/fresh-event-source")
    degraded_source_definition_id: str = _seed_uuid("source/degraded-incident-source")
    cyber_event_id: str = _seed_uuid("event/cloud-security-summit")
    event_participant_id: str = _seed_uuid("event-participant/morgan-lee")
    security_incident_id: str = _seed_uuid("incident/example-ransomware")
    review_incident_id: str = _seed_uuid("incident/nimbus-phishing")
    watch_target_id: str = _seed_uuid("watch/example-industries")
    approve_review_candidate_id: str = _seed_uuid("review/approve-incident")
    reject_review_candidate_id: str = _seed_uuid("review/reject-incident")
    export_crm_target_id: str = _seed_uuid("crm-target/export-ready")
    retry_crm_target_id: str = _seed_uuid("crm-target/retry-demo")
    meeting_crm_target_id: str = _seed_uuid("crm-target/meeting-demo")
    crm_export_batch_id: str = _seed_uuid("crm-export-batch/retryable")
    crm_export_item_id: str = _seed_uuid("crm-export-item/retryable")
    account_id: str = _seed_uuid("account/example-industries")
    contact_id: str = _seed_uuid("contact/taylor-ng")
    sequence_id: str = _seed_uuid("sequence/incident-follow-up")
    sequence_step_id: str = _seed_uuid("sequence-step/initial")
    active_sequence_enrollment_id: str = _seed_uuid("sequence-enrollment/active")
    paused_sequence_enrollment_id: str = _seed_uuid("sequence-enrollment/paused")
    meeting_handoff_id: str = _seed_uuid("meeting/security-discovery")
    meeting_prep_packet_id: str = _seed_uuid("meeting-prep/security-discovery")
    meeting_follow_up_task_id: str = _seed_uuid("meeting-follow-up/security-discovery")


DEMO_SEED_IDS = DemoSeedIds()
DEMO_SEED_REPORTING_RESOURCES = (
    "source_definitions",
    "cyber_events",
    "event_participants",
    "security_incidents",
    "watch_targets",
    "review_candidates",
    "crm_targets",
    "crm_export_batches",
    "crm_export_items",
    "accounts",
    "contacts",
    "sequences",
    "sequence_steps",
    "sequence_enrollments",
    "meeting_handoffs",
    "meeting_prep_packets",
    "meeting_follow_up_tasks",
)


class DemoSeedSafetyError(RuntimeError):
    """Raised when demo seed is requested in a non-local environment."""


def assert_demo_seed_allowed(settings: Settings) -> None:
    if settings.environment in {"local", "dev"}:
        return
    if os.environ.get("GHOSTRECON_ALLOW_DEMO_SEED") == "1":
        return
    raise DemoSeedSafetyError(
        "refusing to seed demo data outside local/dev; set "
        "GHOSTRECON_ALLOW_DEMO_SEED=1 to override"
    )


async def seed_demo_data(settings: Settings | None = None) -> DemoSeedIds:
    resolved = settings or get_settings()
    assert_demo_seed_allowed(resolved)
    async with session_scope(resolved) as session:
        await _upsert_demo_records(session)
    return DEMO_SEED_IDS


async def _upsert_demo_records(session: AsyncSession) -> None:
    now = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    event_start = now + timedelta(days=30)
    incident_observed = now - timedelta(days=5)
    stale_success = now - timedelta(days=4)

    fresh_source = await _source(
        session,
        DEMO_SEED_IDS.fresh_source_definition_id,
        now=now,
        name="GhostRecon Local Demo Fresh Event Source",
        source_kind="event",
        adapter_type="fixture",
        operating_state="enabled",
        last_success_at=now,
        consecutive_failures=0,
        last_error=None,
        checkpoint_state={"cursor": "events-demo-2026-01-15", "seeded": True},
    )
    degraded_source = await _source(
        session,
        DEMO_SEED_IDS.degraded_source_definition_id,
        now=now,
        name="GhostRecon Local Demo Degraded Incident Source",
        source_kind="incident",
        adapter_type="fixture",
        operating_state="degraded",
        last_success_at=stale_success,
        consecutive_failures=2,
        last_error="Synthetic selector failure for stale/degraded dashboard demo.",
        checkpoint_state={"cursor": "incidents-demo-2026-01-11", "seeded": True},
    )
    await session.flush()

    event = await _get_or_create(session, CyberEvent, DEMO_SEED_IDS.cyber_event_id)
    event.name = "Cloud Security Summit Demo"
    event.event_series_key = "cloud-security-summit-demo"
    event.external_id = "demo-event-001"
    event.canonical_url = "https://ghostrecon.local/demo/events/cloud-security-summit"
    event.original_start = event_start.isoformat()
    event.original_end = (event_start + timedelta(days=2)).isoformat()
    event.source_timezone = "UTC"
    event.iana_timezone = "UTC"
    event.timezone_status = "resolved"
    event.starts_at_utc = event_start
    event.ends_at_utc = event_start + timedelta(days=2)
    event.event_format = "physical"
    event.venue_name = "Demo Convention Center"
    event.city = "Zurich"
    event.region = "ZH"
    event.country = "CH"
    event.virtual_url = None
    event.topics = ["cloud security", "incident response", "identity"]
    event.organizers = [{"name": "GhostRecon Demo Team"}]
    event.confidence = 92
    event.canonical_state = "canonical"
    event.dedupe_key = "demo:sprint15:event:cloud-security-summit"
    event.source_definition_id = fresh_source.id
    event.source_item_ids = []
    event.created_at = now
    event.updated_at = now
    await session.flush()

    participant = await _get_or_create(
        session, EventParticipant, DEMO_SEED_IDS.event_participant_id
    )
    participant.cyber_event_id = event.id
    participant.source_definition_id = fresh_source.id
    participant.source_item_id = None
    participant.source_participant_id = "demo-participant-001"
    participant.published_name = "Morgan Lee"
    participant.organization = "Example Industries"
    participant.published_role = "Director of Security Operations"
    participant.participant_type = "speaker"
    participant.profile_url = "https://ghostrecon.local/demo/people/morgan-lee"
    participant.reuse_state = "allowed"
    participant.reuse_evidence = {"basis": "synthetic local fixture"}
    participant.contact_extraction_allowed = True
    participant.crm_export_allowed = True
    participant.resolution_confidence = 94
    participant.dedupe_key = "demo:sprint15:participant:morgan-lee"
    participant.created_at = now
    participant.updated_at = now

    incident = await _get_or_create(
        session, SecurityIncident, DEMO_SEED_IDS.security_incident_id
    )
    _apply_incident(
        incident,
        now=now,
        observed_at=incident_observed,
        title="Example Industries ransomware exposure",
        affected_companies=["Example Industries"],
        affected_domains=["example-industries.test"],
        incident_type="ransomware",
        attack_vector="identity_compromise",
        status="candidate",
        confidence=88,
        dedupe_key="demo:sprint15:incident:example-industries-ransomware",
        source_definition_id=degraded_source.id,
    )

    review_incident = await _get_or_create(
        session, SecurityIncident, DEMO_SEED_IDS.review_incident_id
    )
    _apply_incident(
        review_incident,
        now=now,
        observed_at=incident_observed - timedelta(days=2),
        title="Nimbus Retail phishing campaign mention",
        affected_companies=["Nimbus Retail"],
        affected_domains=["nimbus-retail.test"],
        incident_type="phishing",
        attack_vector="credential_harvesting",
        status="candidate",
        confidence=61,
        dedupe_key="demo:sprint15:incident:nimbus-retail-phishing",
        source_definition_id=degraded_source.id,
    )
    await session.flush()

    watch = await _get_or_create(session, WatchTarget, DEMO_SEED_IDS.watch_target_id)
    watch.target_type = "company"
    watch.canonical_target_key = "example-industries"
    watch.display_name = "Example Industries"
    watch.query_config = {"domains": ["example-industries.test"], "topics": ["ransomware"]}
    watch.enabled = True
    watch.owner = "demo-analyst"
    watch.origin_incident_id = incident.id
    watch.created_by = "demo-seed"
    watch.version = 1
    watch.created_at = now
    watch.updated_at = now

    account = await _get_or_create(session, Account, DEMO_SEED_IDS.account_id)
    account.crm_account_id = "attio-demo-account-example-industries"
    account.domain = "example-industries.test"
    account.company_name = "Example Industries"
    account.hq_country = "US"
    account.employee_count = 1800
    account.revenue_band = "100m-500m"
    account.industry = "Manufacturing"
    account.sub_industry = "Industrial equipment"
    account.tech_stack = {"cloud": ["aws"], "identity": ["okta"]}
    account.security_stack = {"siem": "demo-siem"}
    account.intent_topics = ["identity hardening", "incident response"]
    account.territory = "NA enterprise"
    account.owner_id = "demo-ae"
    account.named_account_flag = True
    account.priority_tier = "tier_1"
    account.fit_score = 86
    account.intent_score = 79
    account.composite_score = 83
    account.last_signal_at = incident_observed
    account.created_at = now
    account.updated_at = now
    await session.flush()

    contact = await _get_or_create(session, Contact, DEMO_SEED_IDS.contact_id)
    contact.crm_contact_id = "attio-demo-contact-taylor-ng"
    contact.account_id = account.id
    contact.full_name = "Taylor Ng"
    contact.title = "VP Security"
    contact.seniority = "executive"
    contact.function = "security"
    contact.email = "taylor.ng@example-industries.test"
    contact.email_status = "verified"
    contact.phone = None
    contact.linkedin_url = "https://ghostrecon.local/demo/people/taylor-ng"
    contact.timezone = "America/New_York"
    contact.persona_type = "economic_buyer"
    contact.buying_role = "decision_maker"
    contact.last_enriched_at = now
    contact.do_not_contact_flag = False
    contact.lawful_basis = "legitimate_interest"
    contact.source_vendor = "ghostrecon-demo"
    contact.source_confidence = 97
    contact.source_url = "https://ghostrecon.local/demo/contacts/taylor-ng"
    contact.source_definition_id = fresh_source.id
    contact.source_item_ids = []
    contact.origin_type = "security_incident"
    contact.origin_id = incident.id
    contact.source_policy_snapshot = {"lawful_basis": "synthetic_demo"}
    contact.review_status = "approved"
    contact.review_reason = None
    contact.idempotency_key = "demo:sprint15:contact:taylor-ng"
    contact.version = 1
    contact.created_at = now
    contact.updated_at = now
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
    await session.flush()

    export_target = await _crm_target(
        session,
        DEMO_SEED_IDS.export_crm_target_id,
        now=now,
        review_candidate_id=approve_review.id,
        target_type="security_incident",
        target_id=incident.id,
        origin_id=incident.id,
        source_definition_id=degraded_source.id,
        status="pending_export",
        export_status="not_exported",
        idempotency_key="demo:sprint15:crm-target:export-example-industries",
    )
    retry_target = await _crm_target(
        session,
        DEMO_SEED_IDS.retry_crm_target_id,
        now=now,
        review_candidate_id=reject_review.id,
        target_type="security_incident",
        target_id=review_incident.id,
        origin_id=review_incident.id,
        source_definition_id=degraded_source.id,
        status="pending_export",
        export_status="failed_retryable",
        idempotency_key="demo:sprint15:crm-target:retry-nimbus-retail",
    )
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

    await _crm_export_batch(session, now=now, target=retry_target)
    sequence = await _sequence(session, now=now)
    step = await _sequence_step(session, now=now, sequence=sequence)
    await session.flush()

    active_enrollment = await _sequence_enrollment(
        session,
        DEMO_SEED_IDS.active_sequence_enrollment_id,
        now=now,
        sequence=sequence,
        crm_target=meeting_target,
        account=account,
        contact=contact,
        status="active",
        next_step_at=now + timedelta(hours=4),
        pause_reason=None,
        idempotency_key="demo:sprint15:sequence-enrollment:active",
    )
    await _sequence_enrollment(
        session,
        DEMO_SEED_IDS.paused_sequence_enrollment_id,
        now=now,
        sequence=sequence,
        crm_target=export_target,
        account=account,
        contact=contact,
        status="paused",
        next_step_at=None,
        pause_reason="Synthetic pause state for resume demo.",
        idempotency_key="demo:sprint15:sequence-enrollment:paused",
    )
    await session.flush()

    meeting = await _meeting(
        session,
        now=now,
        crm_target=meeting_target,
        sequence_enrollment=active_enrollment,
        account=account,
        contact=contact,
    )
    await _meeting_prep_packet(session, now=now, meeting=meeting, account=account, contact=contact)
    await _meeting_follow_up_task(session, now=now, meeting=meeting)

    _ = step


async def _source(
    session: AsyncSession,
    record_id: str,
    *,
    now: datetime,
    name: str,
    source_kind: str,
    adapter_type: str,
    operating_state: str,
    last_success_at: datetime,
    consecutive_failures: int,
    last_error: str | None,
    checkpoint_state: dict[str, object],
) -> SourceDefinition:
    source = await _get_or_create(session, SourceDefinition, record_id)
    source.name = name
    source.source_kind = source_kind
    source.adapter_type = adapter_type
    source.base_url = "https://ghostrecon.local/demo"
    source.owner = "demo"
    source.query_scope = {"fixture": "sprint-15", "kind": source_kind}
    source.credentials_ref = None
    source.rate_limit_policy = {"requests_per_minute": 60}
    source.polling_interval_seconds = 86400
    source.freshness_slo_seconds = 86400
    source.checkpoint_strategy = "manual"
    source.checkpoint_state = checkpoint_state
    source.retry_budget = 1
    source.policy_state = "allowed"
    source.policy_evidence = {"basis": "local deterministic demo fixture"}
    source.policy_reviewed_at = now
    source.participant_reuse_state = "allowed"
    source.participant_reuse_evidence = {"basis": "synthetic local fixture"}
    source.content_storage_policy = "metadata_excerpt"
    source.default_language = "en"
    source.expected_timezone = "UTC"
    source.enabled = True
    source.operating_state = operating_state
    source.last_fetch_at = now
    source.last_success_at = last_success_at
    source.last_error_at = now if last_error else None
    source.last_error = last_error
    source.consecutive_failures = consecutive_failures
    source.created_at = now
    source.updated_at = now
    return source


def _apply_incident(
    incident: SecurityIncident,
    *,
    now: datetime,
    observed_at: datetime,
    title: str,
    affected_companies: list[str],
    affected_domains: list[str],
    incident_type: str,
    attack_vector: str,
    status: str,
    confidence: int,
    dedupe_key: str,
    source_definition_id: str,
) -> None:
    incident.status = status
    incident.title = title
    incident.affected_companies = affected_companies
    incident.affected_domains = affected_domains
    incident.incident_type = incident_type
    incident.attack_vector = attack_vector
    incident.first_observed_at = observed_at
    incident.last_observed_at = observed_at + timedelta(days=1)
    incident.geography = ["US"]
    incident.languages = ["en"]
    incident.confidence = confidence
    incident.evidence_article_ids = []
    incident.evidence_source_item_ids = []
    incident.evidence_families = ["demo-authoritative-disclosure"]
    incident.corroboration_method = "none"
    incident.analyst_decision_ref = None
    incident.canonical_state = "canonical"
    incident.dedupe_key = dedupe_key
    incident.source_definition_id = source_definition_id
    incident.source_item_ids = []
    incident.version = 1
    incident.created_at = now
    incident.updated_at = now


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
) -> ReviewCandidate:
    review = await _get_or_create(session, ReviewCandidate, record_id)
    review.candidate_type = "incident_corroboration"
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
    item.provider_object = "security_incidents"
    item.provider_record_id = None
    item.provider_list_id = None
    item.provider_list_entry_id = None
    item.stable_match_key = f"ghostrecon_incident:{target.target_id}"
    item.status = "failed_retryable"
    item.attempt_count = 1
    item.last_error = "Synthetic Attio rate limit for retry demo."
    item.retry_after_seconds = 60
    item.reconciliation_state = "not_required"
    item.created_at = now - timedelta(hours=2)
    item.updated_at = now - timedelta(hours=1)


async def _sequence(session: AsyncSession, *, now: datetime) -> Sequence:
    sequence = await _get_or_create(session, Sequence, DEMO_SEED_IDS.sequence_id)
    sequence.name = "Incident Follow-up Demo"
    sequence.owner_id = "demo-ae"
    sequence.channel = "email"
    sequence.status = "active"
    sequence.rate_limit_policy = {"per_domain_per_day": 10, "per_sender_per_day": 25}
    sequence.idempotency_key = "demo:sprint15:sequence:incident-follow-up"
    sequence.created_at = now
    sequence.updated_at = now
    return sequence


async def _sequence_step(
    session: AsyncSession,
    *,
    now: datetime,
    sequence: Sequence,
) -> SequenceStep:
    step = await _get_or_create(session, SequenceStep, DEMO_SEED_IDS.sequence_step_id)
    step.sequence_id = sequence.id
    step.step_order = 1
    step.channel = "email"
    step.delay_seconds = 0
    step.subject_template = "Following up on your incident response priorities"
    step.body_template = "Hi {{first_name}}, sharing a concise incident-readiness brief."
    step.active = True
    step.created_at = now
    step.updated_at = now
    return step


async def _sequence_enrollment(
    session: AsyncSession,
    record_id: str,
    *,
    now: datetime,
    sequence: Sequence,
    crm_target: CrmTarget,
    account: Account,
    contact: Contact,
    status: str,
    next_step_at: datetime | None,
    pause_reason: str | None,
    idempotency_key: str,
) -> SequenceEnrollment:
    enrollment = await _get_or_create(session, SequenceEnrollment, record_id)
    enrollment.sequence_id = sequence.id
    enrollment.crm_target_id = crm_target.id
    enrollment.contact_id = contact.id
    enrollment.account_id = account.id
    enrollment.status = status
    enrollment.approval_actor = "demo-analyst"
    enrollment.approval_reason = "Synthetic local outreach approval for demo."
    enrollment.current_step_order = 1
    enrollment.next_step_at = next_step_at
    enrollment.pause_reason = pause_reason
    enrollment.policy_snapshot = {"lawful_basis": "synthetic_demo", "suppression": "clear"}
    enrollment.idempotency_key = idempotency_key
    enrollment.version = 1
    enrollment.created_at = now
    enrollment.updated_at = now
    enrollment.completed_at = None
    return enrollment


async def _meeting(
    session: AsyncSession,
    *,
    now: datetime,
    crm_target: CrmTarget,
    sequence_enrollment: SequenceEnrollment,
    account: Account,
    contact: Contact,
) -> MeetingHandoff:
    meeting = await _get_or_create(session, MeetingHandoff, DEMO_SEED_IDS.meeting_handoff_id)
    meeting.crm_target_id = crm_target.id
    meeting.sequence_enrollment_id = sequence_enrollment.id
    meeting.account_id = account.id
    meeting.contact_id = contact.id
    meeting.status = "scheduled"
    meeting.subject = "Example Industries security discovery"
    meeting.description = "Synthetic meeting handoff for the local GhostRecon demo."
    meeting.location = "Google Meet"
    meeting.start_at = now + timedelta(days=3, hours=2)
    meeting.end_at = now + timedelta(days=3, hours=3)
    meeting.timezone = "America/New_York"
    meeting.attendees = [
        {"email": contact.email, "display_name": contact.full_name},
        {"email": "demo-ae@ghostrecon.local", "display_name": "Demo AE"},
    ]
    meeting.calendar_provider = "google"
    meeting.calendar_id = "demo-calendar"
    meeting.provider_event_id = "demo-google-event-security-discovery"
    meeting.provider_html_link = "https://calendar.google.com/calendar/event?eid=demo"
    meeting.provider_payload = {"fixture": "sprint-15"}
    meeting.outcome_status = None
    meeting.outcome_notes = None
    meeting.next_steps = []
    meeting.crm_sync_status = "failed_retryable"
    meeting.crm_sync_error = "Synthetic CRM sync timeout for retry demo."
    meeting.crm_retry_after_seconds = 120
    meeting.policy_snapshot = {"lawful_basis": "synthetic_demo", "suppression": "clear"}
    meeting.idempotency_key = "demo:sprint15:meeting:security-discovery"
    meeting.version = 1
    meeting.created_at = now
    meeting.updated_at = now
    return meeting


async def _meeting_prep_packet(
    session: AsyncSession,
    *,
    now: datetime,
    meeting: MeetingHandoff,
    account: Account,
    contact: Contact,
) -> None:
    packet = await _get_or_create(
        session, MeetingPrepPacket, DEMO_SEED_IDS.meeting_prep_packet_id
    )
    packet.meeting_id = meeting.id
    packet.account_summary = (
        "Example Industries is a tier-1 manufacturing account with recent ransomware "
        "exposure and active identity-hardening intent."
    )
    packet.stakeholder_map = [
        {"name": contact.full_name, "role": contact.title, "buying_role": contact.buying_role}
    ]
    packet.likely_security_priorities = [
        "identity compromise containment",
        "ransomware tabletop readiness",
        "executive incident reporting",
    ]
    packet.suggested_questions = [
        "Which identity controls changed after the incident?",
        "Where does incident response reporting slow down today?",
    ]
    packet.risks = ["CRM sync is retryable in this fixture."]
    packet.source_snapshot = {
        "account_id": account.id,
        "meeting_id": meeting.id,
        "source": "synthetic_demo",
    }
    packet.generated_by = "demo-seed"
    packet.idempotency_key = "demo:sprint15:meeting-prep:security-discovery"
    packet.created_at = now
    packet.updated_at = now


async def _meeting_follow_up_task(
    session: AsyncSession,
    *,
    now: datetime,
    meeting: MeetingHandoff,
) -> None:
    task = await _get_or_create(
        session, MeetingFollowUpTask, DEMO_SEED_IDS.meeting_follow_up_task_id
    )
    task.meeting_id = meeting.id
    task.title = "Send incident readiness checklist"
    task.description = "Share the short checklist referenced in the prep packet."
    task.owner = "demo-ae"
    task.due_at = now + timedelta(days=4)
    task.status = "open"
    task.crm_sync_status = "pending"
    task.provider_task_id = None
    task.last_error = None
    task.idempotency_key = "demo:sprint15:meeting-follow-up:security-discovery"
    task.created_at = now
    task.updated_at = now


def _selection_hash(target_ids: list[str]) -> str:
    payload = json.dumps(sorted(target_ids), separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


async def _get_or_create(session: AsyncSession, model: type[Any], record_id: str) -> Any:
    record = await session.get(model, record_id)
    if record is not None:
        return record
    record = model(id=record_id)
    session.add(record)
    return record


async def _seeded_counts(settings: Settings) -> dict[str, int]:
    async with session_scope(settings) as session:
        counts = {
            "source_definitions": await _count_seeded(session, SourceDefinition),
            "cyber_events": await _count_seeded(session, CyberEvent),
            "event_participants": await _count_seeded(session, EventParticipant),
            "security_incidents": await _count_seeded(session, SecurityIncident),
            "watch_targets": await _count_seeded(session, WatchTarget),
            "review_candidates": await _count_seeded(session, ReviewCandidate),
            "crm_targets": await _count_seeded(session, CrmTarget),
            "crm_export_batches": await _count_seeded(session, CrmExportBatch),
            "crm_export_items": await _count_seeded(session, CrmExportItem),
            "accounts": await _count_seeded(session, Account),
            "contacts": await _count_seeded(session, Contact),
            "sequences": await _count_seeded(session, Sequence),
            "sequence_steps": await _count_seeded(session, SequenceStep),
            "sequence_enrollments": await _count_seeded(session, SequenceEnrollment),
            "meeting_handoffs": await _count_seeded(session, MeetingHandoff),
            "meeting_prep_packets": await _count_seeded(session, MeetingPrepPacket),
            "meeting_follow_up_tasks": await _count_seeded(session, MeetingFollowUpTask),
        }
    return counts


async def _count_seeded(session: AsyncSession, model: type[Any]) -> int:
    result = await session.execute(
        select(model).where(model.id.in_(DEMO_SEED_IDS.__dict__.values()))
    )
    return len(list(result.scalars()))


async def async_main() -> None:
    settings = get_settings()
    ids = await seed_demo_data(settings)
    counts = await _seeded_counts(settings)
    print("Seeded deterministic local demo data:")
    for table_name in DEMO_SEED_REPORTING_RESOURCES:
        print(f"  {table_name}: {counts[table_name]}")
    print(f"  cyber_event_id: {ids.cyber_event_id}")
    print(f"  security_incident_id: {ids.security_incident_id}")
    print(f"  meeting_handoff_id: {ids.meeting_handoff_id}")
    print(f"  crm_export_batch_id: {ids.crm_export_batch_id}")


def main() -> None:
    try:
        asyncio.run(async_main())
    except DemoSeedSafetyError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
