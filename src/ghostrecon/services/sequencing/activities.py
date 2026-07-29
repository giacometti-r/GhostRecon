from __future__ import annotations

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    SequenceActivityActionRequest,
    SequenceActivityOut,
    SequenceActivityScheduleMeetingRequest,
)
from ghostrecon.models.db import (
    SequenceEnrollment,
    SequenceStep,
    SequenceStepActivity,
)


async def get_sequence_activity(
    activity_id: str,
    *,
    settings: Settings | None = None,
) -> SequenceActivityOut | None:
    async with session_scope(settings) as session:
        activity = await session.get(SequenceStepActivity, activity_id)
        if activity is None:
            return None
        return await _activity_to_model_with_display(session, activity)


async def complete_sequence_activity(
    activity_id: str,
    request: SequenceActivityActionRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SequenceActivityOut | None:
    async with session_scope(settings) as session:
        activity = await session.get(SequenceStepActivity, activity_id)
        if activity is None:
            return None
        if activity.status not in {"pending", "scheduled"}:
            raise ValueError(f"cannot complete {activity.status} activity")
        enrollment = await session.get(SequenceEnrollment, activity.enrollment_id)
        step = await session.get(SequenceStep, activity.sequence_step_id)
        if enrollment is None or step is None:
            raise ValueError("activity is missing sequence context")
        now = utcnow()
        activity.status = "completed"
        activity.completed_by = actor
        activity.completed_at = now
        activity.metadata_payload = {
            **dict(activity.metadata_payload or {}),
            **dict(request.metadata),
            "completion_reason": request.reason,
        }
        activity.updated_at = now
        await _advance_enrollment(session, enrollment, step)
        return await _activity_to_model_with_display(session, activity)


async def schedule_sequence_meeting_activity(
    activity_id: str,
    request: SequenceActivityScheduleMeetingRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SequenceActivityOut | None:
    async with session_scope(settings) as session:
        activity = await session.get(SequenceStepActivity, activity_id)
        if activity is None:
            return None
        if activity.channel != "google_meet":
            raise ValueError("activity is not a Google Meet step")
        if activity.status not in {"pending", "scheduled"}:
            raise ValueError(f"cannot schedule {activity.status} activity")
        enrollment = await session.get(SequenceEnrollment, activity.enrollment_id)
        if enrollment is None:
            raise ValueError("activity is missing enrollment")
        metadata = dict(activity.metadata_payload or {})
        meeting_context = {
            "crm_target_id": enrollment.crm_target_id,
            "sequence_enrollment_id": enrollment.id,
            "account_id": enrollment.account_id,
            "contact_id": enrollment.contact_id,
            "policy_snapshot": dict(enrollment.policy_snapshot or {}),
        }

    from ghostrecon.models.api import MeetingCreateRequest
    from ghostrecon.services.meeting import create_meeting

    meeting = await create_meeting(
        MeetingCreateRequest(
            crm_target_id=str(meeting_context["crm_target_id"]),
            sequence_enrollment_id=str(meeting_context["sequence_enrollment_id"]),
            account_id=meeting_context["account_id"],
            contact_id=meeting_context["contact_id"],
            subject=request.subject or str(metadata.get("meeting_subject") or "Security discovery"),
            description=request.description or str(metadata.get("meeting_description") or ""),
            location=request.location,
            start_at=request.start_at,
            end_at=request.end_at,
            timezone=request.timezone,
            attendees=request.attendees,
            policy_snapshot=dict(meeting_context["policy_snapshot"]),
            send_updates=request.send_updates,
        ),
        actor=actor,
        idempotency_key=f"sequence-meeting:{activity_id}",
        settings=settings,
    )
    async with session_scope(settings) as session:
        activity = await session.get(SequenceStepActivity, activity_id)
        if activity is None:
            raise ValueError("activity disappeared during meeting scheduling")
        enrollment = await session.get(SequenceEnrollment, activity.enrollment_id)
        step = await session.get(SequenceStep, activity.sequence_step_id)
        if enrollment is None or step is None:
            raise ValueError("activity disappeared during meeting scheduling")
        now = utcnow()
        activity.meeting_handoff_id = meeting.id
        activity.status = "scheduled"
        activity.completed_by = actor
        activity.completed_at = now
        activity.updated_at = now
        await _advance_enrollment(session, enrollment, step)
        return await _activity_to_model_with_display(session, activity)


from .common import utcnow  # noqa: E402
from .serializers import _activity_to_model_with_display  # noqa: E402
from .state import _advance_enrollment  # noqa: E402
