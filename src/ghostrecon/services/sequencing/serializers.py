from __future__ import annotations

from typing import Any
from uuid import uuid4

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.configuration import assert_adapter_allowed
from ghostrecon.models.api import (
    InboundEmailEventOut,
    OutboundEmailOut,
    SequenceActivityOut,
    SequenceEmailAlertOut,
    SequenceEnrollmentOut,
    SequenceOut,
    SequenceStepOut,
)
from ghostrecon.models.db import (
    Account,
    Contact,
    InboundEmailEvent,
    OutboundEmail,
    Sequence,
    SequenceEmailAlert,
    SequenceEnrollment,
    SequenceStep,
    SequenceStepActivity,
)
from ghostrecon.services.sequence_adapters import (
    ImapPoller,
    StdlibImapPoller,
)


async def poll_inbound_email_events(
    *,
    limit: int = 50,
    settings: Settings | None = None,
    poller: ImapPoller | None = None,
) -> dict[str, object]:
    resolved = settings or get_settings()
    imap_poller = poller or StdlibImapPoller(resolved)
    assert_adapter_allowed(resolved, imap_poller, "imap_provider")
    events = imap_poller.poll(limit=limit)
    processed = []
    for event in events:
        key = f"inbound_email:{event.event_type.value}:{event.message_id or uuid4()}"
        processed.append(
            (await process_inbound_email_event(event, idempotency_key=key, settings=resolved)).id
        )
    return {"processed": len(processed), "event_ids": processed}


def sequence_step_to_model(step: SequenceStep) -> SequenceStepOut:
    return SequenceStepOut(
        id=step.id,
        sequence_id=step.sequence_id,
        step_order=step.step_order,
        channel=step.channel,
        delay_seconds=step.delay_seconds,
        subject_template=step.subject_template,
        body_template=step.body_template,
        requires_approval=step.requires_approval,
        step_metadata=step.step_metadata or {},
        definition_version=step.definition_version,
        active=step.active,
        created_at=step.created_at,
        updated_at=step.updated_at,
    )


def sequence_to_model(sequence: Sequence, steps: list[SequenceStep]) -> SequenceOut:
    return SequenceOut(
        id=sequence.id,
        name=sequence.name,
        owner_id=sequence.owner_id,
        channel=sequence.channel,
        status=sequence.status,
        rate_limit_policy=sequence.rate_limit_policy or {},
        definition_version=sequence.definition_version,
        created_at=sequence.created_at,
        updated_at=sequence.updated_at,
        steps=[sequence_step_to_model(step) for step in steps],
    )


def outbound_email_to_api(outbound: OutboundEmail) -> dict[str, object]:
    return {
        "id": outbound.id,
        "enrollment_id": outbound.enrollment_id,
        "sequence_step_id": outbound.sequence_step_id,
        "contact_id": outbound.contact_id,
        "channel": outbound.channel,
        "to_email": outbound.to_email,
        "from_email": outbound.from_email,
        "subject": outbound.subject,
        "status": outbound.status,
        "provider_message_id": outbound.provider_message_id,
        "attempt_count": outbound.attempt_count,
        "last_error": outbound.last_error,
        "retry_after_seconds": outbound.retry_after_seconds,
        "scheduled_at": outbound.scheduled_at,
        "sent_at": outbound.sent_at,
        "created_at": outbound.created_at,
        "updated_at": outbound.updated_at,
    }


def outbound_email_to_model(outbound: OutboundEmail) -> OutboundEmailOut:
    return OutboundEmailOut.model_validate(outbound_email_to_api(outbound))


def sequence_enrollment_to_api(enrollment: SequenceEnrollment) -> dict[str, object]:
    return {
        "id": enrollment.id,
        "sequence_id": enrollment.sequence_id,
        "crm_target_id": enrollment.crm_target_id,
        "contact_id": enrollment.contact_id,
        "account_id": enrollment.account_id,
        "status": enrollment.status,
        "approval_actor": enrollment.approval_actor,
        "approval_reason": enrollment.approval_reason,
        "current_step_order": enrollment.current_step_order,
        "definition_version": enrollment.definition_version,
        "next_step_at": enrollment.next_step_at,
        "pause_reason": enrollment.pause_reason,
        "policy_snapshot": enrollment.policy_snapshot or {},
        "version": enrollment.version,
        "created_at": enrollment.created_at,
        "updated_at": enrollment.updated_at,
        "completed_at": enrollment.completed_at,
    }


def sequence_enrollment_to_model(
    enrollment: SequenceEnrollment,
    outbound_emails: list[OutboundEmail] | None = None,
    display: dict[str, object] | None = None,
) -> SequenceEnrollmentOut:
    payload = sequence_enrollment_to_api(enrollment)
    payload.update(display or {})
    payload["outbound_emails"] = [
        outbound_email_to_api(outbound) for outbound in outbound_emails or []
    ]
    return SequenceEnrollmentOut.model_validate(payload)


def sequence_email_alert_to_api(alert: SequenceEmailAlert) -> dict[str, object]:
    return {
        "id": alert.id,
        "enrollment_id": alert.enrollment_id,
        "recipient_email": alert.recipient_email,
        "subject": alert.subject,
        "body": alert.body,
        "send_at": alert.send_at,
        "status": alert.status,
        "actor": alert.actor,
        "provider_message_id": alert.provider_message_id,
        "last_error": alert.last_error,
        "sent_at": alert.sent_at,
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
    }


def sequence_email_alert_to_model(alert: SequenceEmailAlert) -> SequenceEmailAlertOut:
    return SequenceEmailAlertOut.model_validate(sequence_email_alert_to_api(alert))


def sequence_activity_to_api(activity: SequenceStepActivity) -> dict[str, object]:
    return {
        "id": activity.id,
        "enrollment_id": activity.enrollment_id,
        "sequence_step_id": activity.sequence_step_id,
        "outbound_email_id": activity.outbound_email_id,
        "meeting_handoff_id": activity.meeting_handoff_id,
        "step_order": activity.step_order,
        "channel": activity.channel,
        "status": activity.status,
        "due_at": activity.due_at,
        "approved_by": activity.approved_by,
        "approved_at": activity.approved_at,
        "completed_by": activity.completed_by,
        "completed_at": activity.completed_at,
        "metadata": activity.metadata_payload or {},
        "created_at": activity.created_at,
        "updated_at": activity.updated_at,
    }


async def _activity_to_model_with_display(
    session: Any,
    activity: SequenceStepActivity,
) -> SequenceActivityOut:
    payload = sequence_activity_to_api(activity)
    enrollment = await session.get(SequenceEnrollment, activity.enrollment_id)
    sequence = await session.get(Sequence, enrollment.sequence_id) if enrollment else None
    contact = await session.get(Contact, enrollment.contact_id) if enrollment else None
    account = (
        await session.get(Account, enrollment.account_id)
        if enrollment and enrollment.account_id
        else None
    )
    payload.update(
        {
            "sequence_id": sequence.id if sequence else None,
            "sequence_name": sequence.name if sequence else None,
            "contact_name": contact.full_name if contact else None,
            "contact_email": contact.email if contact else None,
            "account_name": account.company_name if account else None,
        }
    )
    return SequenceActivityOut.model_validate(payload)


def inbound_event_to_api(event: InboundEmailEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "enrollment_id": event.enrollment_id,
        "outbound_email_id": event.outbound_email_id,
        "event_type": event.event_type,
        "from_email": event.from_email,
        "to_email": event.to_email,
        "message_id": event.message_id,
        "provider_payload": event.provider_payload or {},
        "occurred_at": event.occurred_at,
        "created_at": event.created_at,
    }


def inbound_event_to_model(event: InboundEmailEvent) -> InboundEmailEventOut:
    return InboundEmailEventOut.model_validate(inbound_event_to_api(event))


from .inbound import process_inbound_email_event  # noqa: E402
