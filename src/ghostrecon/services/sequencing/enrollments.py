from __future__ import annotations

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName
from ghostrecon.models.api import (
    SequenceActivityList,
    SequenceEnrollmentActionRequest,
    SequenceEnrollmentCreateRequest,
    SequenceEnrollmentList,
    SequenceEnrollmentOut,
)
from ghostrecon.models.db import (
    CrmTarget,
    Sequence,
    SequenceEnrollment,
    SequenceStepActivity,
)


async def create_sequence_enrollment(
    request: SequenceEnrollmentCreateRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> SequenceEnrollmentOut:
    if not request.outreach_approved:
        raise ValueError("separate outreach approval is required")

    async with session_scope(settings) as session:
        existing = await session.scalar(
            select(SequenceEnrollment).where(SequenceEnrollment.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return await _enrollment_to_model_with_emails(session, existing)

        sequence = await session.get(Sequence, request.sequence_id)
        if sequence is None or sequence.status != "active":
            raise ValueError("active sequence not found")
        steps = await _sequence_steps(session, sequence.id)
        if not steps:
            raise ValueError("sequence has no active steps")

        target = await session.get(CrmTarget, request.crm_target_id)
        if target is None:
            raise ValueError("crm target not found")
        if target.status != "exported" or target.export_status != "exported":
            raise ValueError("crm target must be exported before sequence enrollment")

        contact = await _contact_for_target(session, target, request.contact_id)
        _require_sendable_contact(contact)
        account_id = request.account_id or contact.account_id
        domain = _domain_from_email(contact.email)
        suppression = await _suppression_allowed(
            session,
            email=contact.email,
            domain=domain,
            contact_id=contact.id,
            channel=sequence.channel,
        )
        if not suppression.allowed:
            raise ValueError(suppression.reason or "suppression blocks outreach")

        now = utcnow()
        policy_snapshot = dict(target.policy_snapshot or {})
        policy_snapshot.update(dict(request.policy_snapshot))
        enrollment = SequenceEnrollment(
            sequence_id=sequence.id,
            crm_target_id=target.id,
            contact_id=contact.id,
            account_id=account_id,
            status="active",
            approval_actor=actor,
            approval_reason=request.approval_reason,
            current_step_order=steps[0].step_order,
            definition_version=sequence.definition_version,
            next_step_at=request.start_at or now,
            pause_reason=None,
            policy_snapshot=policy_snapshot,
            idempotency_key=idempotency_key,
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(enrollment)
        await session.flush()
        _enqueue_event(
            session,
            EventName.SEQUENCE_ENROLLED,
            "sequence_enrollment",
            enrollment.id,
            sequence_enrollment_to_api(enrollment),
            f"sequence.enrolled:{enrollment.id}",
        )
        return await _enrollment_to_model_with_emails(session, enrollment)


async def get_sequence_enrollment(
    enrollment_id: str,
    *,
    settings: Settings | None = None,
) -> SequenceEnrollmentOut | None:
    async with session_scope(settings) as session:
        enrollment = await session.get(SequenceEnrollment, enrollment_id)
        if enrollment is None:
            return None
        return await _enrollment_to_model_with_emails(session, enrollment)


async def list_sequence_enrollments(
    *,
    status: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> SequenceEnrollmentList:
    async with session_scope(settings) as session:
        query = (
            select(SequenceEnrollment).order_by(SequenceEnrollment.created_at.desc()).limit(limit)
        )
        if status:
            query = query.where(_fuzzy(SequenceEnrollment.status, status))
        result = await session.execute(query)
        enrollments = [
            await _enrollment_to_model_with_emails(session, enrollment)
            for enrollment in result.scalars()
        ]
        return SequenceEnrollmentList(enrollments=enrollments)


async def list_sequence_activities(
    *,
    status: str | None = None,
    channel: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> SequenceActivityList:
    async with session_scope(settings) as session:
        query = (
            select(SequenceStepActivity)
            .order_by(SequenceStepActivity.created_at.desc())
            .limit(limit)
        )
        if status:
            query = query.where(_fuzzy(SequenceStepActivity.status, status))
        if channel:
            query = query.where(_fuzzy(SequenceStepActivity.channel, channel))
        result = await session.execute(query)
        activities = [
            await _activity_to_model_with_display(session, activity)
            for activity in result.scalars()
        ]
        return SequenceActivityList(activities=activities)


async def pause_sequence_enrollment(
    enrollment_id: str,
    request: SequenceEnrollmentActionRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SequenceEnrollmentOut | None:
    _ = actor
    return await _set_enrollment_status(
        enrollment_id,
        status="paused",
        reason=request.reason,
        event_name=EventName.SEQUENCE_PAUSED,
        settings=settings,
    )


async def resume_sequence_enrollment(
    enrollment_id: str,
    request: SequenceEnrollmentActionRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SequenceEnrollmentOut | None:
    _ = actor, request
    async with session_scope(settings) as session:
        enrollment = await session.get(SequenceEnrollment, enrollment_id)
        if enrollment is None:
            return None
        if enrollment.status in TERMINAL_ENROLLMENT_STATUSES:
            raise ValueError(f"cannot resume {enrollment.status} enrollment")
        enrollment.status = "active"
        enrollment.pause_reason = None
        enrollment.next_step_at = enrollment.next_step_at or utcnow()
        enrollment.version += 1
        enrollment.updated_at = utcnow()
        return await _enrollment_to_model_with_emails(session, enrollment)


async def cancel_sequence_enrollment(
    enrollment_id: str,
    request: SequenceEnrollmentActionRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SequenceEnrollmentOut | None:
    _ = actor
    return await _set_enrollment_status(
        enrollment_id,
        status="canceled",
        reason=request.reason,
        event_name=None,
        settings=settings,
    )


from .common import TERMINAL_ENROLLMENT_STATUSES, utcnow  # noqa: E402
from .eligibility import _fuzzy  # noqa: E402
from .policy import _enqueue_event  # noqa: E402
from .queries import (  # noqa: E402
    _contact_for_target,
    _enrollment_to_model_with_emails,
    _require_sendable_contact,
    _sequence_steps,
    _set_enrollment_status,
    _suppression_allowed,
)
from .serializers import _activity_to_model_with_display, sequence_enrollment_to_api  # noqa: E402
from .templating import _domain_from_email  # noqa: E402
