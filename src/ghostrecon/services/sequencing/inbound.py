from __future__ import annotations

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName
from ghostrecon.models.api import (
    InboundEmailEventCreate,
    InboundEmailEventOut,
    InboundEmailEventType,
    UnsubscribeRequest,
)
from ghostrecon.models.db import (
    InboundEmailEvent,
    SequenceEnrollment,
)


async def process_inbound_email_event(
    request: InboundEmailEventCreate,
    *,
    idempotency_key: str,
    settings: Settings | None = None,
) -> InboundEmailEventOut:
    async with session_scope(settings) as session:
        existing = await session.scalar(
            select(InboundEmailEvent).where(InboundEmailEvent.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return inbound_event_to_model(existing)

        outbound = await _find_outbound_for_inbound(session, request)
        enrollment = (
            await session.get(SequenceEnrollment, outbound.enrollment_id)
            if outbound is not None
            else await _find_enrollment_by_email(session, request.from_email)
        )
        now = request.occurred_at or utcnow()
        event = InboundEmailEvent(
            enrollment_id=enrollment.id if enrollment else None,
            outbound_email_id=outbound.id if outbound else None,
            event_type=request.event_type.value,
            from_email=str(request.from_email).lower() if request.from_email else None,
            to_email=str(request.to_email).lower() if request.to_email else None,
            message_id=request.message_id,
            provider_payload=dict(request.provider_payload),
            idempotency_key=idempotency_key,
            occurred_at=now,
            created_at=utcnow(),
        )
        session.add(event)
        await session.flush()

        if request.event_type == InboundEmailEventType.REPLY:
            if enrollment:
                _complete_enrollment(session, enrollment)
            _enqueue_event(
                session,
                EventName.REPLY_RECEIVED,
                "inbound_email_event",
                event.id,
                inbound_event_to_api(event),
                f"reply.received:{event.id}",
            )
        elif request.event_type == InboundEmailEventType.BOUNCE:
            if outbound:
                outbound.status = "failed_terminal"
                outbound.last_error = "bounce received"
                outbound.updated_at = utcnow()
            if enrollment:
                enrollment.status = "paused"
                enrollment.pause_reason = "bounce received"
                enrollment.updated_at = utcnow()
            _enqueue_event(
                session,
                EventName.BOUNCE_RECEIVED,
                "inbound_email_event",
                event.id,
                inbound_event_to_api(event),
                f"bounce.received:{event.id}",
            )
        elif request.event_type == InboundEmailEventType.UNSUBSCRIBE:
            email = str(request.from_email or request.to_email or "").lower()
            if email:
                channel = str(request.provider_payload.get("channel") or "email")
                reason = str(request.provider_payload.get("reason") or "unsubscribe")
                await _create_unsubscribe_suppression(
                    session,
                    email=email,
                    channel=channel,
                    reason=reason,
                    source_event=event,
                    enrollment=enrollment,
                )
            if enrollment:
                enrollment.status = "suppressed"
                enrollment.pause_reason = "unsubscribe"
                enrollment.completed_at = utcnow()
                enrollment.updated_at = utcnow()
            _enqueue_event(
                session,
                EventName.UNSUBSCRIBE_RECEIVED,
                "inbound_email_event",
                event.id,
                inbound_event_to_api(event),
                f"unsubscribe.received:{event.id}",
            )
        return inbound_event_to_model(event)


async def process_unsubscribe(
    request: UnsubscribeRequest,
    *,
    idempotency_key: str,
    settings: Settings | None = None,
) -> InboundEmailEventOut:
    return await process_inbound_email_event(
        InboundEmailEventCreate(
            event_type=InboundEmailEventType.UNSUBSCRIBE,
            from_email=request.email,
            provider_payload={
                **dict(request.provider_payload),
                "domain": request.domain,
                "reason": request.reason,
                "channel": request.channel,
            },
        ),
        idempotency_key=idempotency_key,
        settings=settings,
    )


from .common import utcnow  # noqa: E402
from .policy import (  # noqa: E402
    _create_unsubscribe_suppression,
    _enqueue_event,
    _find_enrollment_by_email,
    _find_outbound_for_inbound,
)
from .serializers import inbound_event_to_api, inbound_event_to_model  # noqa: E402
from .state import _complete_enrollment  # noqa: E402
