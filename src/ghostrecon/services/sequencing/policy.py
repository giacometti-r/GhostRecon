from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    InboundEmailEventCreate,
)
from ghostrecon.models.db import (
    InboundEmailEvent,
    OutboundEmail,
    OutboxEvent,
    Sequence,
    SequenceEnrollment,
    SequenceSuppressionEvent,
    Suppression,
)


async def _rate_limit_blocker(
    session: Any,
    *,
    to_email: str,
    from_email: str,
    channel: str,
    sequence: Sequence,
    settings: Settings,
) -> str | None:
    policy = sequence.rate_limit_policy or {}
    domain_limit = int(policy.get("domain_daily_limit") or settings.sequence_domain_daily_limit)
    sender_limit = int(policy.get("sender_daily_limit") or settings.sequence_sender_daily_limit)
    channel_limit = int(policy.get("channel_daily_limit") or settings.sequence_channel_daily_limit)
    domain = _domain_from_email(to_email)
    since = utcnow() - timedelta(days=1)
    result = await session.execute(
        select(OutboundEmail)
        .where(OutboundEmail.status == "sent")
        .where(OutboundEmail.channel == channel)
        .where(OutboundEmail.sent_at >= since)
    )
    sent = list(result.scalars())
    domain_count = len([email for email in sent if _domain_from_email(email.to_email) == domain])
    sender_count = len([email for email in sent if email.from_email.lower() == from_email.lower()])
    channel_count = len(sent)
    if domain_count >= domain_limit:
        return f"domain daily rate limit reached for {domain}"
    if sender_count >= sender_limit:
        return f"sender daily rate limit reached for {from_email}"
    if channel_count >= channel_limit:
        return f"channel daily rate limit reached for {channel}"
    return None


async def _find_outbound_for_inbound(
    session: Any,
    request: InboundEmailEventCreate,
) -> OutboundEmail | None:
    if request.provider_message_id:
        outbound = await session.scalar(
            select(OutboundEmail)
            .where(OutboundEmail.provider_message_id == request.provider_message_id)
            .order_by(OutboundEmail.sent_at.desc())
            .limit(1)
        )
        if outbound is not None:
            return outbound
    email = str(request.from_email or "").lower()
    if not email:
        return None
    return await session.scalar(
        select(OutboundEmail)
        .where(OutboundEmail.to_email == email)
        .where(OutboundEmail.status == "sent")
        .order_by(OutboundEmail.sent_at.desc())
        .limit(1)
    )


async def _find_enrollment_by_email(
    session: Any,
    email: str | None,
) -> SequenceEnrollment | None:
    if not email:
        return None
    outbound = await session.scalar(
        select(OutboundEmail)
        .where(OutboundEmail.to_email == str(email).lower())
        .order_by(OutboundEmail.created_at.desc())
        .limit(1)
    )
    return await session.get(SequenceEnrollment, outbound.enrollment_id) if outbound else None


async def _create_unsubscribe_suppression(
    session: Any,
    *,
    email: str,
    channel: str,
    reason: str,
    source_event: InboundEmailEvent,
    enrollment: SequenceEnrollment | None,
) -> None:
    domain = _domain_from_email(email)
    suppression = await session.scalar(
        select(Suppression)
        .where(Suppression.email == email.lower())
        .where(Suppression.channel == channel.lower())
        .where(Suppression.active.is_(True))
        .limit(1)
    )
    if suppression is None:
        suppression = Suppression(
            email=email.lower(),
            domain=domain,
            channel=channel.lower(),
            reason=reason,
            source="unsubscribe",
            active=True,
            policy_snapshot={"source_event_id": source_event.id},
            idempotency_key=f"unsubscribe:{channel.lower()}:{email.lower()}",
        )
        session.add(suppression)
        await session.flush()
        _enqueue_event(
            session,
            EventName.SUPPRESSION_CREATED,
            "suppression",
            suppression.id,
            {
                "id": suppression.id,
                "email": suppression.email,
                "domain": suppression.domain,
                "channel": suppression.channel,
                "reason": suppression.reason,
                "source": suppression.source,
            },
            f"suppression.created:{suppression.id}",
        )
    session.add(
        SequenceSuppressionEvent(
            enrollment_id=enrollment.id if enrollment else None,
            suppression_id=suppression.id,
            email=email.lower(),
            domain=domain,
            channel=channel.lower(),
            reason=reason,
            source_event_id=source_event.id,
        )
    )


def _enqueue_event(
    session: Any,
    event_name: EventName,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, object],
    idempotency_key: str,
) -> OutboxEvent:
    event = new_event(
        event_name=event_name,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        source_service=SEQUENCING_SERVICE_NAME,
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


from .common import SEQUENCING_SERVICE_NAME, utcnow  # noqa: E402
from .templating import _domain_from_email  # noqa: E402
