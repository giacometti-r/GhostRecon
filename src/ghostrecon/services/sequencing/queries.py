from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName
from ghostrecon.models.api import (
    SequenceEnrollmentOut,
    SuppressionCheckRequest,
)
from ghostrecon.models.db import (
    Account,
    Contact,
    CrmTarget,
    EmailCandidateRecord,
    OutboundEmail,
    Sequence,
    SequenceEnrollment,
    SequenceStep,
    SequenceStepActivity,
    Suppression,
)
from ghostrecon.services.governance import evaluate_suppression


async def _sequence_steps(
    session: Any,
    sequence_id: str,
    definition_version: int | None = None,
) -> list[SequenceStep]:
    if definition_version is None:
        sequence = await session.get(Sequence, sequence_id)
        definition_version = sequence.definition_version if sequence else 1
    result = await session.execute(
        select(SequenceStep)
        .where(SequenceStep.sequence_id == sequence_id)
        .where(SequenceStep.definition_version == definition_version)
        .where(SequenceStep.active.is_(True))
        .order_by(SequenceStep.step_order)
    )
    return list(result.scalars())


def _requires_approval(channel: str, explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    return channel == "email"


async def _activity_for_step(
    session: Any,
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    *,
    status: str,
    outbound_email_id: str | None = None,
) -> SequenceStepActivity:
    key = f"sequence_activity:{enrollment.id}:{step.id}"
    existing = await session.scalar(
        select(SequenceStepActivity).where(SequenceStepActivity.idempotency_key == key)
    )
    if existing is not None:
        if outbound_email_id and not existing.outbound_email_id:
            existing.outbound_email_id = outbound_email_id
        return existing
    now = utcnow()
    activity = SequenceStepActivity(
        enrollment_id=enrollment.id,
        sequence_step_id=step.id,
        outbound_email_id=outbound_email_id,
        meeting_handoff_id=None,
        step_order=step.step_order,
        channel=step.channel,
        status=status,
        due_at=now,
        approved_by=None,
        approved_at=None,
        completed_by=None,
        completed_at=None,
        metadata_payload=dict(step.step_metadata or {}),
        idempotency_key=key,
        created_at=now,
        updated_at=now,
    )
    session.add(activity)
    await session.flush()
    return activity


async def _enrollment_to_model_with_emails(
    session: Any,
    enrollment: SequenceEnrollment,
) -> SequenceEnrollmentOut:
    email_result = await session.execute(
        select(OutboundEmail)
        .where(OutboundEmail.enrollment_id == enrollment.id)
        .order_by(OutboundEmail.created_at)
    )
    sequence = await session.get(Sequence, enrollment.sequence_id)
    contact = await session.get(Contact, enrollment.contact_id)
    account = await session.get(Account, enrollment.account_id) if enrollment.account_id else None
    target = await session.get(CrmTarget, enrollment.crm_target_id)
    display = {
        "sequence_name": sequence.name if sequence else None,
        "contact_name": contact.full_name if contact else None,
        "contact_email": contact.email if contact else None,
        "account_name": account.company_name if account else None,
        "account_domain": account.domain if account else None,
        "crm_target_summary": _crm_target_summary(target),
    }
    return sequence_enrollment_to_model(enrollment, list(email_result.scalars()), display)


async def _set_enrollment_status(
    enrollment_id: str,
    *,
    status: str,
    reason: str,
    event_name: EventName | None,
    settings: Settings | None,
) -> SequenceEnrollmentOut | None:
    async with session_scope(settings) as session:
        enrollment = await session.get(SequenceEnrollment, enrollment_id)
        if enrollment is None:
            return None
        if enrollment.status in TERMINAL_ENROLLMENT_STATUSES and status != enrollment.status:
            raise ValueError(f"cannot change {enrollment.status} enrollment")
        enrollment.status = status
        enrollment.pause_reason = reason
        enrollment.version += 1
        enrollment.updated_at = utcnow()
        if status in TERMINAL_ENROLLMENT_STATUSES:
            enrollment.completed_at = utcnow()
        if event_name is not None:
            _enqueue_event(
                session,
                event_name,
                "sequence_enrollment",
                enrollment.id,
                sequence_enrollment_to_api(enrollment),
                f"{event_name.value}:{enrollment.id}:{enrollment.version}",
            )
        return await _enrollment_to_model_with_emails(session, enrollment)


async def _contact_for_target(
    session: Any,
    target: CrmTarget,
    requested_contact_id: str | None,
) -> Contact:
    if requested_contact_id:
        contact = await session.get(Contact, requested_contact_id)
        if contact is None:
            raise ValueError("contact not found")
        return contact
    if target.target_type in {"contact", "incident_contact"}:
        contact = await session.get(Contact, target.target_id)
        if contact is not None:
            return contact
    if target.target_type == "email_candidate":
        candidate = await session.get(EmailCandidateRecord, target.target_id)
        if candidate is not None and candidate.contact_id:
            contact = await session.get(Contact, candidate.contact_id)
            if contact is not None:
                return contact
    raise ValueError("sequence enrollment requires a contact")


def _require_sendable_contact(contact: Contact) -> None:
    if contact.do_not_contact_flag:
        raise ValueError("contact is marked do-not-contact")
    if not contact.email:
        raise ValueError("contact has no email")
    if contact.email_status != "verified":
        raise ValueError("contact email must be verified before outreach")
    if not contact.lawful_basis:
        raise ValueError("contact is missing lawful basis")


async def _suppression_allowed(
    session: Any,
    *,
    email: str | None,
    domain: str | None,
    contact_id: str | None,
    channel: str,
) -> Any:
    baseline = evaluate_suppression(
        SuppressionCheckRequest(
            email=email,
            domain=domain,
            contact_id=contact_id,
            channel=channel,
        )
    )
    if not baseline.allowed:
        return baseline
    matches = []
    if email:
        matches.append(Suppression.email == email.lower())
    if domain:
        matches.append(Suppression.domain == domain.lower())
    if contact_id:
        matches.append(Suppression.contact_id == contact_id)
    if not matches:
        return baseline
    suppression = await session.scalar(
        select(Suppression)
        .where(Suppression.active.is_(True))
        .where(Suppression.channel == channel.lower())
        .where(or_(Suppression.expires_at.is_(None), Suppression.expires_at > utcnow()))
        .where(or_(*matches))
        .limit(1)
    )
    if suppression is None:
        return baseline
    return baseline.model_copy(update={"allowed": False, "reason": suppression.reason})


async def _step_for_order(
    session: Any,
    sequence_id: str,
    step_order: int,
    definition_version: int | None = None,
) -> SequenceStep | None:
    query = (
        select(SequenceStep)
        .where(SequenceStep.sequence_id == sequence_id)
        .where(SequenceStep.step_order == step_order)
        .where(SequenceStep.active.is_(True))
    )
    if definition_version is not None:
        query = query.where(SequenceStep.definition_version == definition_version)
    else:
        query = query.order_by(SequenceStep.definition_version.desc())
    return await session.scalar(query.limit(1))


async def _outbound_for_step(
    session: Any,
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    contact: Contact,
    account: Account | None,
    from_email: str,
) -> OutboundEmail:
    key = f"sequence_email:{enrollment.id}:{step.id}"
    existing = await session.scalar(
        select(OutboundEmail).where(OutboundEmail.idempotency_key == key)
    )
    if existing is not None:
        return existing
    now = utcnow()
    outbound = OutboundEmail(
        enrollment_id=enrollment.id,
        sequence_step_id=step.id,
        contact_id=contact.id,
        channel=step.channel,
        to_email=contact.email.lower(),
        from_email=from_email,
        subject=_render_template(step.subject_template or "", contact, account),
        body=_render_template(step.body_template or "", contact, account),
        status="pending",
        idempotency_key=key,
        attempt_count=0,
        scheduled_at=enrollment.next_step_at or now,
        created_at=now,
        updated_at=now,
    )
    session.add(outbound)
    await session.flush()
    return outbound


from .common import TERMINAL_ENROLLMENT_STATUSES, utcnow  # noqa: E402
from .policy import _enqueue_event  # noqa: E402
from .serializers import sequence_enrollment_to_api, sequence_enrollment_to_model  # noqa: E402
from .templating import _crm_target_summary, _render_template  # noqa: E402
