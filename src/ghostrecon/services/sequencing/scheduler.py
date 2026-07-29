from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.db import (
    Account,
    Contact,
    Sequence,
    SequenceEnrollment,
)
from ghostrecon.services.sequence_adapters import (
    SmtpSender,
)


async def process_due_sequence_steps(
    *,
    limit: int = 50,
    settings: Settings | None = None,
    sender: SmtpSender | None = None,
) -> dict[str, object]:
    resolved = settings or get_settings()
    now = utcnow()
    async with session_scope(resolved) as session:
        result = await session.execute(
            select(SequenceEnrollment)
            .where(SequenceEnrollment.status.in_(ACTIVE_ENROLLMENT_STATUSES))
            .where(SequenceEnrollment.next_step_at.is_not(None))
            .where(SequenceEnrollment.next_step_at <= now)
            .order_by(SequenceEnrollment.next_step_at)
            .limit(limit)
        )
        enrollment_ids = [enrollment.id for enrollment in result.scalars()]

    outcomes = []
    for enrollment_id in enrollment_ids:
        outcomes.append(
            await send_next_sequence_step(
                enrollment_id,
                settings=resolved,
                sender=sender,
            )
        )
    return {"processed": len(outcomes), "outcomes": outcomes}


async def send_next_sequence_step(
    enrollment_id: str,
    *,
    settings: Settings | None = None,
    sender: SmtpSender | None = None,
) -> dict[str, object]:
    resolved = settings or get_settings()
    _ = sender
    async with session_scope(resolved) as session:
        enrollment = await session.get(SequenceEnrollment, enrollment_id)
        if enrollment is None:
            raise ValueError("sequence enrollment not found")
        if enrollment.status != "active":
            return {"enrollment_id": enrollment.id, "status": enrollment.status}

        sequence = await session.get(Sequence, enrollment.sequence_id)
        if sequence is None or sequence.status != "active":
            await _pause_for_policy(session, enrollment, "sequence is not active")
            return {"enrollment_id": enrollment.id, "status": "paused"}

        step = await _step_for_order(
            session,
            enrollment.sequence_id,
            enrollment.current_step_order,
            enrollment.definition_version,
        )
        if step is None:
            _complete_enrollment(session, enrollment)
            return {"enrollment_id": enrollment.id, "status": "completed"}

        contact = await session.get(Contact, enrollment.contact_id)
        if contact is None:
            await _pause_for_policy(session, enrollment, "contact no longer exists")
            return {"enrollment_id": enrollment.id, "status": "paused"}
        try:
            _require_sendable_contact(contact)
        except ValueError as exc:
            await _pause_for_policy(session, enrollment, str(exc))
            return {"enrollment_id": enrollment.id, "status": "paused", "reason": str(exc)}

        domain = _domain_from_email(contact.email)
        suppression = await _suppression_allowed(
            session,
            email=contact.email,
            domain=domain,
            contact_id=contact.id,
            channel=step.channel,
        )
        if not suppression.allowed:
            await _suppress_enrollment(session, enrollment, contact, suppression.reason)
            return {
                "enrollment_id": enrollment.id,
                "status": "suppressed",
                "reason": suppression.reason,
            }

        if step.channel != "email":
            activity = await _activity_for_step(session, enrollment, step, status="pending")
            enrollment.next_step_at = None
            enrollment.updated_at = utcnow()
            return {
                "enrollment_id": enrollment.id,
                "activity_id": activity.id,
                "status": activity.status,
                "channel": activity.channel,
            }

        from_email = resolved.smtp_from_address.lower()
        rate_limit_reason = await _rate_limit_blocker(
            session,
            to_email=contact.email,
            from_email=from_email,
            channel=step.channel,
            sequence=sequence,
            settings=resolved,
        )
        if rate_limit_reason:
            enrollment.next_step_at = utcnow() + timedelta(
                seconds=resolved.sequence_retry_after_seconds
            )
            enrollment.pause_reason = rate_limit_reason
            enrollment.updated_at = utcnow()
            return {
                "enrollment_id": enrollment.id,
                "status": "rate_limited",
                "reason": rate_limit_reason,
            }

        account = (
            await session.get(Account, enrollment.account_id) if enrollment.account_id else None
        )
        outbound = await _outbound_for_step(session, enrollment, step, contact, account, from_email)
        outbound.status = "pending_approval"
        outbound.updated_at = utcnow()
        activity = await _activity_for_step(
            session,
            enrollment,
            step,
            status="pending_approval",
            outbound_email_id=outbound.id,
        )
        enrollment.next_step_at = None
        enrollment.updated_at = utcnow()
        return {
            "enrollment_id": enrollment.id,
            "outbound_email_id": outbound.id,
            "activity_id": activity.id,
            "status": activity.status,
        }


from .common import ACTIVE_ENROLLMENT_STATUSES, utcnow  # noqa: E402
from .policy import _rate_limit_blocker  # noqa: E402
from .queries import (  # noqa: E402
    _activity_for_step,
    _outbound_for_step,
    _require_sendable_contact,
    _step_for_order,
    _suppression_allowed,
)
from .state import _complete_enrollment, _pause_for_policy, _suppress_enrollment  # noqa: E402
from .templating import _domain_from_email  # noqa: E402
