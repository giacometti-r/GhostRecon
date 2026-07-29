from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.db import (
    OutboxEvent,
    SequenceEnrollment,
)

from .common import MEETING_SERVICE_NAME, SEQUENCING_SERVICE_NAME, utcnow


def _complete_sequence_for_meeting(session: Any, enrollment: SequenceEnrollment) -> None:
    enrollment.status = "completed"
    enrollment.next_step_at = None
    enrollment.pause_reason = "meeting_booked"
    enrollment.completed_at = utcnow()
    enrollment.version += 1
    enrollment.updated_at = utcnow()
    _enqueue_event(
        session,
        EventName.SEQUENCE_COMPLETED,
        "sequence_enrollment",
        enrollment.id,
        {
            "id": enrollment.id,
            "sequence_id": enrollment.sequence_id,
            "crm_target_id": enrollment.crm_target_id,
            "contact_id": enrollment.contact_id,
            "account_id": enrollment.account_id,
            "status": enrollment.status,
            "approval_actor": enrollment.approval_actor,
            "approval_reason": enrollment.approval_reason,
            "current_step_order": enrollment.current_step_order,
            "next_step_at": enrollment.next_step_at,
            "pause_reason": enrollment.pause_reason,
            "policy_snapshot": enrollment.policy_snapshot or {},
            "version": enrollment.version,
            "created_at": enrollment.created_at,
            "updated_at": enrollment.updated_at,
            "completed_at": enrollment.completed_at,
        },
        f"sequence.completed:{enrollment.id}:{enrollment.version}",
        source_service=SEQUENCING_SERVICE_NAME,
    )


def _enqueue_event(
    session: Any,
    event_name: EventName,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, object],
    idempotency_key: str,
    *,
    source_service: str = MEETING_SERVICE_NAME,
) -> OutboxEvent:
    event = new_event(
        event_name=event_name,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        source_service=source_service,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    outbox = OutboxEvent(
        event_name=event.event_name,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        idempotency_key=event.idempotency_key,
        payload=event.model_dump(mode="json"),
    )
    session.add(outbox)
    return outbox


def _domain_from_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[1].lower()


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()
