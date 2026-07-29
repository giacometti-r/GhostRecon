from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ghostrecon.models.api import (
    MeetingFollowUpTaskOut,
    MeetingHandoffOut,
    MeetingPrepPacketOut,
)
from ghostrecon.models.db import (
    MeetingFollowUpTask,
    MeetingHandoff,
    MeetingPrepPacket,
)


def meeting_to_api(meeting: MeetingHandoff) -> dict[str, object]:
    return {
        "id": meeting.id,
        "crm_target_id": meeting.crm_target_id,
        "sequence_enrollment_id": meeting.sequence_enrollment_id,
        "account_id": meeting.account_id,
        "contact_id": meeting.contact_id,
        "status": meeting.status,
        "subject": meeting.subject,
        "description": meeting.description,
        "location": meeting.location,
        "start_at": meeting.start_at,
        "end_at": meeting.end_at,
        "timezone": meeting.timezone,
        "attendees": meeting.attendees or [],
        "calendar_provider": meeting.calendar_provider,
        "calendar_id": meeting.calendar_id,
        "provider_event_id": meeting.provider_event_id,
        "provider_html_link": meeting.provider_html_link,
        "outcome_status": meeting.outcome_status,
        "outcome_notes": meeting.outcome_notes,
        "next_steps": meeting.next_steps or [],
        "crm_sync_status": meeting.crm_sync_status,
        "crm_sync_error": meeting.crm_sync_error,
        "crm_retry_after_seconds": meeting.crm_retry_after_seconds,
        "policy_snapshot": meeting.policy_snapshot or {},
        "version": meeting.version,
        "created_at": meeting.created_at,
        "updated_at": meeting.updated_at,
    }


def meeting_to_model(
    meeting: MeetingHandoff,
    *,
    prep_packet: MeetingPrepPacket | None = None,
    follow_up_tasks: list[MeetingFollowUpTask] | None = None,
) -> MeetingHandoffOut:
    payload = meeting_to_api(meeting)
    payload["prep_packet"] = (
        meeting_prep_packet_to_api(prep_packet) if prep_packet is not None else None
    )
    payload["follow_up_tasks"] = [
        meeting_follow_up_task_to_api(task) for task in follow_up_tasks or []
    ]
    return MeetingHandoffOut.model_validate(payload)


def meeting_prep_packet_to_api(packet: MeetingPrepPacket) -> dict[str, object]:
    return {
        "id": packet.id,
        "meeting_id": packet.meeting_id,
        "account_summary": packet.account_summary,
        "stakeholder_map": packet.stakeholder_map or [],
        "likely_security_priorities": packet.likely_security_priorities or [],
        "suggested_questions": packet.suggested_questions or [],
        "risks": packet.risks or [],
        "source_snapshot": packet.source_snapshot or {},
        "generated_by": packet.generated_by,
        "created_at": packet.created_at,
        "updated_at": packet.updated_at,
    }


def meeting_prep_packet_to_model(packet: MeetingPrepPacket) -> MeetingPrepPacketOut:
    return MeetingPrepPacketOut.model_validate(meeting_prep_packet_to_api(packet))


def meeting_follow_up_task_to_api(task: MeetingFollowUpTask) -> dict[str, object]:
    return {
        "id": task.id,
        "meeting_id": task.meeting_id,
        "title": task.title,
        "description": task.description,
        "owner": task.owner,
        "due_at": task.due_at,
        "status": task.status,
        "crm_sync_status": task.crm_sync_status,
        "provider_task_id": task.provider_task_id,
        "last_error": task.last_error,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def meeting_follow_up_task_to_model(task: MeetingFollowUpTask) -> MeetingFollowUpTaskOut:
    return MeetingFollowUpTaskOut.model_validate(meeting_follow_up_task_to_api(task))


async def _meeting_to_model_with_children(
    session: Any,
    meeting: MeetingHandoff,
) -> MeetingHandoffOut:
    packet = await _latest_prep_packet(session, meeting.id)
    result = await session.execute(
        select(MeetingFollowUpTask)
        .where(MeetingFollowUpTask.meeting_id == meeting.id)
        .order_by(MeetingFollowUpTask.created_at.asc(), MeetingFollowUpTask.id.asc())
    )
    return meeting_to_model(
        meeting,
        prep_packet=packet,
        follow_up_tasks=list(result.scalars()),
    )


from .crm_sync import _latest_prep_packet  # noqa: E402
