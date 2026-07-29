from __future__ import annotations

from datetime import timedelta

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.configuration import assert_adapter_allowed
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName
from ghostrecon.models.api import (
    SequenceActivityActionRequest,
    SequenceActivityOut,
)
from ghostrecon.models.db import (
    Account,
    Contact,
    OutboundEmail,
    Sequence,
    SequenceEnrollment,
    SequenceStep,
    SequenceStepActivity,
)
from ghostrecon.services.sequence_adapters import (
    SmtpSender,
    SmtpSendRequest,
    StdlibSmtpSender,
)


async def send_approved_sequence_email(
    activity_id: str,
    request: SequenceActivityActionRequest,
    *,
    actor: str,
    settings: Settings | None = None,
    sender: SmtpSender | None = None,
) -> SequenceActivityOut | None:
    _ = request
    resolved = settings or get_settings()
    smtp_sender = sender or StdlibSmtpSender(resolved)
    assert_adapter_allowed(resolved, smtp_sender, "smtp_provider")
    async with session_scope(resolved) as session:
        activity = await session.get(SequenceStepActivity, activity_id)
        if activity is None:
            return None
        if activity.channel != "email":
            raise ValueError("activity is not an email approval")
        if activity.status not in {"pending_approval", "approved"}:
            raise ValueError(f"cannot approve {activity.status} activity")
        enrollment = await session.get(SequenceEnrollment, activity.enrollment_id)
        step = await session.get(SequenceStep, activity.sequence_step_id)
        if enrollment is None or step is None:
            raise ValueError("activity is missing sequence context")
        if enrollment.status != "active":
            raise ValueError("sequence enrollment is not active")
        sequence = await session.get(Sequence, enrollment.sequence_id)
        contact = await session.get(Contact, enrollment.contact_id)
        if sequence is None or sequence.status != "active":
            await _pause_for_policy(session, enrollment, "sequence is not active")
            raise ValueError("sequence is not active")
        if contact is None:
            await _pause_for_policy(session, enrollment, "contact no longer exists")
            raise ValueError("contact no longer exists")
        _require_sendable_contact(contact)
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
            raise ValueError(suppression.reason or "suppression blocks outreach")
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
            raise ValueError(rate_limit_reason)
        account = (
            await session.get(Account, enrollment.account_id) if enrollment.account_id else None
        )
        outbound = (
            await session.get(OutboundEmail, activity.outbound_email_id)
            if activity.outbound_email_id
            else await _outbound_for_step(session, enrollment, step, contact, account, from_email)
        )
        outbound.attempt_count += 1
        outbound.status = "pending"
        outbound.last_error = None
        outbound.retry_after_seconds = None
        outbound.updated_at = utcnow()
        message_id = f"<ghostrecon-{outbound.id}@local>"

        try:
            result = smtp_sender.send(
                SmtpSendRequest(
                    from_email=outbound.from_email,
                    to_email=outbound.to_email,
                    subject=outbound.subject,
                    body=outbound.body,
                    message_id=message_id,
                )
            )
        except Exception as exc:
            outbound.status = "failed_retryable"
            outbound.last_error = str(exc)
            outbound.retry_after_seconds = resolved.sequence_retry_after_seconds
            outbound.updated_at = utcnow()
            activity.status = "failed"
            activity.metadata_payload = {
                **dict(activity.metadata_payload or {}),
                "last_error": str(exc),
            }
            activity.updated_at = utcnow()
            enrollment.next_step_at = utcnow() + timedelta(
                seconds=resolved.sequence_retry_after_seconds
            )
            enrollment.updated_at = utcnow()
            return await _activity_to_model_with_display(session, activity)

        outbound.status = "sent"
        outbound.provider_message_id = result.provider_message_id
        outbound.sent_at = utcnow()
        outbound.updated_at = utcnow()
        _enqueue_event(
            session,
            EventName.EMAIL_SENT,
            "outbound_email",
            outbound.id,
            outbound_email_to_api(outbound),
            f"email.sent:{outbound.id}:{outbound.attempt_count}",
        )
        await _advance_enrollment(session, enrollment, step)
        activity.status = "completed"
        activity.approved_by = actor
        activity.approved_at = utcnow()
        activity.completed_by = actor
        activity.completed_at = utcnow()
        activity.updated_at = utcnow()
        return await _activity_to_model_with_display(session, activity)


from .common import utcnow  # noqa: E402
from .policy import _enqueue_event, _rate_limit_blocker  # noqa: E402
from .queries import (  # noqa: E402
    _outbound_for_step,
    _require_sendable_contact,
    _suppression_allowed,
)
from .serializers import _activity_to_model_with_display, outbound_email_to_api  # noqa: E402
from .state import _advance_enrollment, _pause_for_policy, _suppress_enrollment  # noqa: E402
from .templating import _domain_from_email  # noqa: E402
