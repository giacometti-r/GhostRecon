from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.configuration import assert_adapter_allowed
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    CalendarAvailabilityRequest,
    CalendarAvailabilityResult,
    MeetingActionRequest,
    MeetingAttendee,
    MeetingHandoffOut,
    SuppressionCheckRequest,
)
from ghostrecon.models.db import (
    Contact,
    MeetingHandoff,
    Suppression,
)
from ghostrecon.services.calendar_adapters import (
    CalendarClient,
    calendar_client_for_settings,
)
from ghostrecon.services.governance import evaluate_suppression


async def cancel_meeting(
    meeting_id: str,
    request: MeetingActionRequest,
    *,
    actor: str,
    settings: Settings | None = None,
    calendar_client: CalendarClient | None = None,
) -> MeetingHandoffOut | None:
    _ = actor
    resolved = settings or get_settings()
    client = calendar_client or calendar_client_for_settings(resolved)
    assert_adapter_allowed(resolved, client, "calendar_provider")
    async with session_scope(resolved) as session:
        meeting = await session.get(MeetingHandoff, meeting_id)
        if meeting is None:
            return None
        if meeting.provider_event_id:
            await client.cancel_event(
                meeting.provider_event_id,
                send_updates=resolved.google_calendar_send_updates,
            )
        meeting.status = "canceled"
        meeting.outcome_status = "disqualified"
        meeting.outcome_notes = request.reason
        meeting.version += 1
        meeting.updated_at = utcnow()
        return await _meeting_to_model_with_children(session, meeting)


async def get_calendar_availability(
    request: CalendarAvailabilityRequest,
    *,
    settings: Settings | None = None,
    calendar_client: CalendarClient | None = None,
) -> CalendarAvailabilityResult:
    if request.time_max <= request.time_min:
        raise ValueError("time_max must be after time_min")
    resolved = settings or get_settings()
    client = calendar_client or calendar_client_for_settings(resolved)
    assert_adapter_allowed(resolved, client, "calendar_provider")
    calendars = await client.get_availability(
        attendees=[str(attendee).lower() for attendee in request.attendees],
        time_min=request.time_min,
        time_max=request.time_max,
        timezone=request.timezone,
    )
    return CalendarAvailabilityResult(calendars=calendars, provider=client.provider)


async def _ensure_invite_allowed(
    session: Any,
    attendees: list[MeetingAttendee],
    contact: Contact | None,
) -> None:
    for attendee in attendees:
        email = str(attendee.email).lower()
        domain = _domain_from_email(email)
        contact_id = (
            contact.id if contact and contact.email and contact.email.lower() == email else None
        )
        baseline = evaluate_suppression(
            SuppressionCheckRequest(
                email=email,
                domain=domain,
                contact_id=contact_id,
                channel="email",
            )
        )
        if not baseline.allowed:
            raise ValueError(baseline.reason or "suppression blocks meeting invite")
        clauses = [Suppression.email == email]
        if domain:
            clauses.append(Suppression.domain == domain)
        if contact_id:
            clauses.append(Suppression.contact_id == contact_id)
        suppression = await session.scalar(
            select(Suppression)
            .where(Suppression.active.is_(True))
            .where(Suppression.channel == "email")
            .where(or_(Suppression.expires_at.is_(None), Suppression.expires_at > utcnow()))
            .where(or_(*clauses))
            .limit(1)
        )
        if suppression is not None:
            raise ValueError(suppression.reason)


from .common import utcnow  # noqa: E402
from .events import _domain_from_email  # noqa: E402
from .serializers import _meeting_to_model_with_children  # noqa: E402
