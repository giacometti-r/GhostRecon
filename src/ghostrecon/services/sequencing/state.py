from __future__ import annotations

from datetime import timedelta
from typing import Any

from ghostrecon.events.contracts import EventName
from ghostrecon.models.db import (
    Contact,
    SequenceEnrollment,
    SequenceStep,
    SequenceSuppressionEvent,
)


async def _advance_enrollment(
    session: Any,
    enrollment: SequenceEnrollment,
    current_step: SequenceStep,
) -> None:
    steps = await _sequence_steps(
        session,
        enrollment.sequence_id,
        enrollment.definition_version,
    )
    next_steps = [step for step in steps if step.step_order > current_step.step_order]
    now = utcnow()
    if not next_steps:
        _complete_enrollment(session, enrollment)
        return
    next_step = next_steps[0]
    enrollment.current_step_order = next_step.step_order
    enrollment.next_step_at = now + timedelta(seconds=next_step.delay_seconds)
    enrollment.version += 1
    enrollment.updated_at = now


def _complete_enrollment(session: Any, enrollment: SequenceEnrollment) -> None:
    enrollment.status = "completed"
    enrollment.next_step_at = None
    enrollment.pause_reason = None
    enrollment.completed_at = utcnow()
    enrollment.version += 1
    enrollment.updated_at = utcnow()
    _enqueue_event(
        session,
        EventName.SEQUENCE_COMPLETED,
        "sequence_enrollment",
        enrollment.id,
        sequence_enrollment_to_api(enrollment),
        f"sequence.completed:{enrollment.id}:{enrollment.version}",
    )


async def _pause_for_policy(
    session: Any,
    enrollment: SequenceEnrollment,
    reason: str,
) -> None:
    enrollment.status = "paused"
    enrollment.pause_reason = reason
    enrollment.version += 1
    enrollment.updated_at = utcnow()
    _enqueue_event(
        session,
        EventName.SEQUENCE_PAUSED,
        "sequence_enrollment",
        enrollment.id,
        sequence_enrollment_to_api(enrollment),
        f"sequence.paused:{enrollment.id}:{enrollment.version}",
    )


async def _suppress_enrollment(
    session: Any,
    enrollment: SequenceEnrollment,
    contact: Contact,
    reason: str | None,
) -> None:
    enrollment.status = "suppressed"
    enrollment.pause_reason = reason or "suppression blocks outreach"
    enrollment.completed_at = utcnow()
    enrollment.version += 1
    enrollment.updated_at = utcnow()
    session.add(
        SequenceSuppressionEvent(
            enrollment_id=enrollment.id,
            email=contact.email.lower() if contact.email else None,
            domain=_domain_from_email(contact.email),
            channel="email",
            reason=enrollment.pause_reason,
        )
    )
    _enqueue_event(
        session,
        EventName.SEQUENCE_PAUSED,
        "sequence_enrollment",
        enrollment.id,
        sequence_enrollment_to_api(enrollment),
        f"sequence.paused:{enrollment.id}:{enrollment.version}",
    )


from .common import utcnow  # noqa: E402
from .policy import _enqueue_event  # noqa: E402
from .queries import _sequence_steps  # noqa: E402
from .serializers import sequence_enrollment_to_api  # noqa: E402
from .templating import _domain_from_email  # noqa: E402
