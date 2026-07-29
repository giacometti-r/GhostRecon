from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.configuration import assert_adapter_allowed
from ghostrecon.events.contracts import EventName
from ghostrecon.models.api import (
    MeetingAttendee,
)
from ghostrecon.models.db import (
    Contact,
    CrmTarget,
    EmailCandidateRecord,
    MeetingFollowUpTask,
    MeetingHandoff,
    MeetingPrepPacket,
)
from ghostrecon.services.crm_attio import (
    CrmClient,
    CrmProviderError,
    CrmSyncPlan,
)


async def _latest_prep_packet(session: Any, meeting_id: str) -> MeetingPrepPacket | None:
    return await session.scalar(
        select(MeetingPrepPacket)
        .where(MeetingPrepPacket.meeting_id == meeting_id)
        .order_by(MeetingPrepPacket.created_at.desc(), MeetingPrepPacket.id.desc())
        .limit(1)
    )


async def _sync_meeting_to_crm(
    session: Any,
    meeting: MeetingHandoff,
    *,
    actor: str,
    settings: Settings,
    client: CrmClient | None,
) -> None:
    tasks = list(
        (
            await session.execute(
                select(MeetingFollowUpTask)
                .where(MeetingFollowUpTask.meeting_id == meeting.id)
                .order_by(MeetingFollowUpTask.created_at.asc())
            )
        ).scalars()
    )
    plan = _crm_sync_plan(meeting, tasks, actor=actor, settings=settings)
    meeting.crm_sync_status = "pending"
    meeting.crm_sync_error = None
    meeting.crm_retry_after_seconds = None
    for task in tasks:
        task.crm_sync_status = "pending"
        task.last_error = None
        task.updated_at = utcnow()
    try:
        from ghostrecon.services.crm_exports.clients import crm_client_for_settings

        crm = client or crm_client_for_settings(settings)
        assert_adapter_allowed(settings, crm, "crm_provider")
        result = await crm.sync(plan)
    except (CrmProviderError, ValueError) as exc:
        retryable = isinstance(exc, CrmProviderError) and exc.retryable
        meeting.crm_sync_status = "failed_retryable" if retryable else "failed_terminal"
        meeting.crm_sync_error = str(exc)
        meeting.crm_retry_after_seconds = (
            exc.retry_after_seconds if isinstance(exc, CrmProviderError) else None
        )
        meeting.status = "failed_sync" if retryable else meeting.status
        meeting.updated_at = utcnow()
        for task in tasks:
            task.crm_sync_status = meeting.crm_sync_status
            task.last_error = str(exc)
            task.updated_at = utcnow()
        return

    meeting.crm_sync_status = "succeeded"
    meeting.crm_sync_error = None
    meeting.crm_retry_after_seconds = None
    meeting.updated_at = utcnow()
    for task in tasks:
        task.crm_sync_status = "succeeded"
        task.provider_task_id = result.provider_record_id
        task.last_error = None
        task.updated_at = utcnow()
    _enqueue_event(
        session,
        EventName.CRM_SYNCED,
        "meeting_handoff",
        meeting.id,
        {
            "meeting_id": meeting.id,
            "provider_record_id": result.provider_record_id,
            "provider_list_entry_id": result.provider_list_entry_id,
            "raw_response": result.raw_response,
        },
        f"crm.synced:meeting:{meeting.id}:{meeting.version}",
        source_service="crm-service",
    )


def _crm_sync_plan(
    meeting: MeetingHandoff,
    tasks: list[MeetingFollowUpTask],
    *,
    actor: str,
    settings: Settings,
) -> CrmSyncPlan:
    return CrmSyncPlan(
        sync_type="meeting_handoff",
        target_id=meeting.id,
        provider_object="meeting_handoffs",
        stable_match_key=f"ghostrecon_meeting:{meeting.id}",
        matching_attribute="ghostrecon_id",
        values={
            "ghostrecon_id": meeting.id,
            "crm_target_id": meeting.crm_target_id,
            "account_id": meeting.account_id,
            "contact_id": meeting.contact_id,
            "subject": meeting.subject,
            "status": meeting.status,
            "start_at": _iso(meeting.start_at),
            "end_at": _iso(meeting.end_at),
            "timezone": meeting.timezone,
            "outcome_status": meeting.outcome_status,
            "outcome_notes": meeting.outcome_notes,
            "next_steps": meeting.next_steps or [],
            "calendar_provider": meeting.calendar_provider,
            "calendar_event_id": meeting.provider_event_id,
            "calendar_link": meeting.provider_html_link,
            "follow_up_tasks": [meeting_follow_up_task_to_api(task) for task in tasks],
            "synced_by": actor,
        },
        list_api_slug=settings.attio_meetings_list_api_slug,
        list_entry_values={
            "meeting_status": meeting.status,
            "outcome_status": meeting.outcome_status,
        },
    )


async def _contact_for_meeting(
    session: Any,
    target: CrmTarget | None,
    requested_contact_id: str | None,
) -> Contact | None:
    if requested_contact_id:
        contact = await session.get(Contact, requested_contact_id)
        if contact is None:
            raise ValueError("contact not found")
        return contact
    if target is None:
        return None
    if target.target_type in {"contact", "incident_contact"}:
        return await session.get(Contact, target.target_id)
    if target.target_type == "email_candidate":
        candidate = await session.get(EmailCandidateRecord, target.target_id)
        if candidate and candidate.contact_id:
            return await session.get(Contact, candidate.contact_id)
    return None


def _meeting_attendees(
    requested: list[MeetingAttendee],
    contact: Contact | None,
) -> list[MeetingAttendee]:
    attendees = list(requested)
    seen = {str(attendee.email).lower() for attendee in attendees}
    if contact and contact.email and contact.email.lower() not in seen:
        attendees.append(
            MeetingAttendee(
                email=contact.email.lower(),
                name=contact.full_name,
                optional=False,
            )
        )
    if not attendees:
        raise ValueError("meeting requires at least one attendee")
    return attendees


from .common import utcnow  # noqa: E402
from .events import _enqueue_event, _iso  # noqa: E402
from .serializers import meeting_follow_up_task_to_api  # noqa: E402
