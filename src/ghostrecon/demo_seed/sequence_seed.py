from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.models.db import (
    Account,
    Contact,
    CrmTarget,
    Sequence,
    SequenceEnrollment,
    SequenceStep,
    SequenceStepActivity,
)

from .crm_seed import _crm_export_batch
from .ids import DEMO_SEED_IDS
from .meeting_seed import _meeting, _meeting_follow_up_task, _meeting_prep_packet
from .persistence import _get_or_create


async def _sequence(session: AsyncSession, *, now: datetime) -> Sequence:
    sequence = await _get_or_create(session, Sequence, DEMO_SEED_IDS.sequence_id)
    sequence.name = "Incident Follow-up Demo"
    sequence.owner_id = "demo-ae"
    sequence.channel = "email"
    sequence.status = "active"
    sequence.rate_limit_policy = {"per_domain_per_day": 10, "per_sender_per_day": 25}
    sequence.definition_version = 1
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
    step.requires_approval = True
    step.step_metadata = {"display_label": "Approved email follow-up"}
    step.definition_version = sequence.definition_version
    step.active = True
    step.created_at = now
    step.updated_at = now
    call_step = await _get_or_create(session, SequenceStep, DEMO_SEED_IDS.sequence_call_step_id)
    call_step.sequence_id = sequence.id
    call_step.step_order = 2
    call_step.channel = "call"
    call_step.delay_seconds = 86400
    call_step.subject_template = None
    call_step.body_template = None
    call_step.requires_approval = False
    call_step.step_metadata = {
        "display_label": "Call security leader",
        "instructions": "Call Taylor and capture identity-hardening priorities.",
    }
    call_step.definition_version = sequence.definition_version
    call_step.active = True
    call_step.created_at = now
    call_step.updated_at = now
    meeting_step = await _get_or_create(
        session,
        SequenceStep,
        DEMO_SEED_IDS.sequence_meeting_step_id,
    )
    meeting_step.sequence_id = sequence.id
    meeting_step.step_order = 3
    meeting_step.channel = "google_meet"
    meeting_step.delay_seconds = 172800
    meeting_step.subject_template = None
    meeting_step.body_template = None
    meeting_step.requires_approval = False
    meeting_step.step_metadata = {
        "display_label": "Book Google Meet",
        "meeting_subject": "Example Industries security discovery",
        "instructions": "Schedule a discovery meeting when the prospect engages.",
    }
    meeting_step.definition_version = sequence.definition_version
    meeting_step.active = True
    meeting_step.created_at = now
    meeting_step.updated_at = now
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
    enrollment.definition_version = sequence.definition_version
    enrollment.next_step_at = next_step_at
    enrollment.pause_reason = pause_reason
    enrollment.policy_snapshot = {"lawful_basis": "synthetic_demo", "suppression": "clear"}
    enrollment.idempotency_key = idempotency_key
    enrollment.version = 1
    enrollment.created_at = now
    enrollment.updated_at = now
    enrollment.completed_at = None
    return enrollment


async def _sequence_activity(
    session: AsyncSession,
    *,
    now: datetime,
    sequence_enrollment: SequenceEnrollment,
    sequence_step: SequenceStep,
) -> None:
    activity = await _get_or_create(
        session,
        SequenceStepActivity,
        DEMO_SEED_IDS.sequence_activity_id,
    )
    activity.enrollment_id = sequence_enrollment.id
    activity.sequence_step_id = sequence_step.id
    activity.outbound_email_id = None
    activity.meeting_handoff_id = None
    activity.step_order = sequence_step.step_order
    activity.channel = sequence_step.channel
    activity.status = "pending_approval"
    activity.due_at = now
    activity.approved_by = None
    activity.approved_at = None
    activity.completed_by = None
    activity.completed_at = None
    activity.metadata_payload = {
        "display_label": "Review approved email",
        "instructions": "Approve the local demo email before the sequence can send.",
    }
    activity.idempotency_key = "demo:sprint21:sequence-activity:email-approval"
    activity.created_at = now
    activity.updated_at = now


async def _seed_sequence_and_meeting(
    session: AsyncSession,
    now: datetime,
    account: Account,
    contact: Contact,
    export_target: CrmTarget,
    retry_target: CrmTarget,
    meeting_target: CrmTarget,
):
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
    await _sequence_activity(
        session,
        now=now,
        sequence_enrollment=active_enrollment,
        sequence_step=step,
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
