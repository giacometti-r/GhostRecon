from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.models.db import (
    Account,
    Contact,
    CrmTarget,
    MeetingFollowUpTask,
    MeetingHandoff,
    MeetingPrepPacket,
    SequenceEnrollment,
)

from .ids import DEMO_SEED_IDS
from .persistence import _get_or_create


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
    packet = await _get_or_create(session, MeetingPrepPacket, DEMO_SEED_IDS.meeting_prep_packet_id)
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
