from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.configuration import assert_adapter_allowed
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName
from ghostrecon.models.api import (
    MeetingCreateRequest,
    MeetingHandoffList,
    MeetingHandoffOut,
    PrepPacket,
    PrepPacketRequest,
)
from ghostrecon.models.db import (
    CrmTarget,
    MeetingHandoff,
    SequenceEnrollment,
)
from ghostrecon.services.calendar_adapters import (
    CalendarClient,
    CalendarEventRequest,
    calendar_client_for_settings,
)


def build_prep_packet(request: PrepPacketRequest) -> PrepPacket:
    account_name = str(
        request.account.get("company_name") or request.account.get("domain") or "Account"
    )
    contacts = [
        f"{contact.get('full_name', 'Unknown')} - {contact.get('title', 'Unknown role')}"
        for contact in request.contacts
    ]
    signal_topics = [
        str(signal.get("signal_topic") or signal.get("signal_type"))
        for signal in request.signals
        if signal.get("signal_topic") or signal.get("signal_type")
    ]

    return PrepPacket(
        account_summary=f"{account_name} has {len(request.contacts)} known stakeholders and "
        f"{len(request.signals)} active signals.",
        stakeholder_map=contacts,
        likely_security_priorities=signal_topics[:5] or ["Confirm current security priorities"],
        suggested_questions=[
            "Which security initiatives are funded this quarter?",
            "What tools or processes are creating the most operational drag?",
            "Which integrations or controls must be validated before a pilot?",
        ],
        risks=[
            "Signal relevance needs human validation before use in messaging",
            "Technical fit should be confirmed by AE/SE discovery",
        ],
    )


async def create_meeting(
    request: MeetingCreateRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
    calendar_client: CalendarClient | None = None,
) -> MeetingHandoffOut:
    _require_time_window(request.start_at, request.end_at)
    resolved = settings or get_settings()
    client = calendar_client or calendar_client_for_settings(resolved)
    assert_adapter_allowed(resolved, client, "calendar_provider")
    async with session_scope(resolved) as session:
        existing = await session.scalar(
            select(MeetingHandoff).where(MeetingHandoff.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return await _meeting_to_model_with_children(session, existing)

        target = await session.get(CrmTarget, request.crm_target_id)
        _require_exported_target(target)
        contact = await _contact_for_meeting(session, target, request.contact_id)
        account_id = request.account_id or (contact.account_id if contact else None)
        attendees = _meeting_attendees(request.attendees, contact)
        await _ensure_invite_allowed(session, attendees, contact)

        enrollment = None
        if request.sequence_enrollment_id:
            enrollment = await session.get(SequenceEnrollment, request.sequence_enrollment_id)
            if enrollment is None:
                raise ValueError("sequence enrollment not found")

        now = utcnow()
        meeting = MeetingHandoff(
            crm_target_id=target.id,
            sequence_enrollment_id=enrollment.id if enrollment else None,
            account_id=account_id,
            contact_id=contact.id if contact else request.contact_id,
            status="scheduled",
            subject=request.subject,
            description=request.description,
            location=request.location,
            start_at=request.start_at,
            end_at=request.end_at,
            timezone=request.timezone,
            attendees=[attendee.model_dump(mode="json") for attendee in attendees],
            calendar_provider=client.provider,
            calendar_id=None,
            provider_event_id=None,
            provider_html_link=None,
            provider_payload={},
            outcome_status=None,
            outcome_notes=None,
            next_steps=[],
            crm_sync_status="pending",
            policy_snapshot={
                **dict(target.policy_snapshot or {}),
                **dict(request.policy_snapshot),
                "booked_by": actor,
            },
            idempotency_key=idempotency_key,
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(meeting)
        await session.flush()

        calendar_result = await client.create_event(
            CalendarEventRequest(
                meeting_id=meeting.id,
                subject=meeting.subject,
                start_at=meeting.start_at,
                end_at=meeting.end_at,
                timezone=meeting.timezone,
                attendees=attendees,
                description=meeting.description,
                location=meeting.location,
                send_updates=(
                    request.send_updates
                    if request.send_updates is not None
                    else resolved.google_calendar_send_updates
                ),
            )
        )
        meeting.calendar_id = calendar_result.calendar_id
        meeting.provider_event_id = calendar_result.provider_event_id
        meeting.provider_html_link = calendar_result.html_link
        meeting.provider_payload = calendar_result.raw_response
        meeting.updated_at = utcnow()

        if enrollment and enrollment.status in ACTIVE_ENROLLMENT_STATUSES:
            _complete_sequence_for_meeting(session, enrollment)
        _enqueue_event(
            session,
            EventName.MEETING_BOOKED,
            "meeting_handoff",
            meeting.id,
            meeting_to_api(meeting),
            f"meeting.booked:{meeting.id}",
        )
        return await _meeting_to_model_with_children(session, meeting)


async def list_meetings(
    *,
    status: str | None = None,
    crm_target_id: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> MeetingHandoffList:
    async with session_scope(settings) as session:
        stmt = select(MeetingHandoff).order_by(
            MeetingHandoff.start_at.desc(),
            MeetingHandoff.id.asc(),
        )
        if status:
            stmt = stmt.where(MeetingHandoff.status == status)
        if crm_target_id:
            stmt = stmt.where(MeetingHandoff.crm_target_id == crm_target_id)
        rows = list((await session.execute(stmt.limit(limit))).scalars())
        meetings = [await _meeting_to_model_with_children(session, meeting) for meeting in rows]
    return MeetingHandoffList(meetings=meetings)


async def get_meeting(
    meeting_id: str,
    *,
    settings: Settings | None = None,
) -> MeetingHandoffOut | None:
    async with session_scope(settings) as session:
        meeting = await session.get(MeetingHandoff, meeting_id)
        if meeting is None:
            return None
        return await _meeting_to_model_with_children(session, meeting)


def _require_exported_target(target: CrmTarget | None) -> None:
    if target is None:
        raise ValueError("crm target not found")
    if target.status != "exported" or target.export_status != "exported":
        raise ValueError("crm target must be exported before meeting handoff")


def _require_time_window(start_at: datetime, end_at: datetime) -> None:
    if end_at <= start_at:
        raise ValueError("end_at must be after start_at")


from .calendar import _ensure_invite_allowed  # noqa: E402
from .common import ACTIVE_ENROLLMENT_STATUSES, utcnow  # noqa: E402
from .crm_sync import _contact_for_meeting, _meeting_attendees  # noqa: E402
from .events import _complete_sequence_for_meeting, _enqueue_event  # noqa: E402
from .serializers import _meeting_to_model_with_children, meeting_to_api  # noqa: E402
