from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    CalendarAvailabilityRequest,
    CalendarAvailabilityResult,
    MeetingActionRequest,
    MeetingAttendee,
    MeetingCreateRequest,
    MeetingFollowUpTaskCreate,
    MeetingFollowUpTaskOut,
    MeetingHandoffList,
    MeetingHandoffOut,
    MeetingOutcomeRequest,
    MeetingPrepPacketOut,
    PrepPacket,
    PrepPacketRequest,
    SuppressionCheckRequest,
)
from ghostrecon.models.db import (
    Account,
    Contact,
    CrmTarget,
    CyberEvent,
    EmailCandidateRecord,
    MeetingFollowUpTask,
    MeetingHandoff,
    MeetingPrepPacket,
    OutboxEvent,
    SecurityIncident,
    SequenceEnrollment,
    Signal,
    Suppression,
)
from ghostrecon.services.calendar_adapters import (
    CalendarClient,
    CalendarEventRequest,
    calendar_client_for_settings,
)
from ghostrecon.services.crm_attio import (
    AttioCrmClient,
    CrmClient,
    CrmProviderError,
    CrmSyncPlan,
)
from ghostrecon.services.governance import evaluate_suppression

MEETING_SERVICE_NAME = "meeting-handoff-service"
SEQUENCING_SERVICE_NAME = "sequencing-service"
ACTIVE_ENROLLMENT_STATUSES = {"active"}


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


async def generate_meeting_prep_packet(
    meeting_id: str,
    *,
    actor: str,
    idempotency_key: str | None = None,
    settings: Settings | None = None,
) -> MeetingHandoffOut | None:
    async with session_scope(settings) as session:
        meeting = await session.get(MeetingHandoff, meeting_id)
        if meeting is None:
            return None
        if idempotency_key:
            existing = await session.scalar(
                select(MeetingPrepPacket).where(
                    MeetingPrepPacket.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                return await _meeting_to_model_with_children(session, meeting)

        existing_latest = await _latest_prep_packet(session, meeting.id)
        if existing_latest is not None and idempotency_key is None:
            return await _meeting_to_model_with_children(session, meeting)

        prep_request, source_snapshot = await _prep_request_for_meeting(session, meeting)
        packet = build_prep_packet(prep_request)
        now = utcnow()
        record = MeetingPrepPacket(
            meeting_id=meeting.id,
            account_summary=packet.account_summary,
            stakeholder_map=list(packet.stakeholder_map),
            likely_security_priorities=list(packet.likely_security_priorities),
            suggested_questions=list(packet.suggested_questions),
            risks=list(packet.risks),
            source_snapshot=source_snapshot,
            generated_by=actor,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        await session.flush()
        _enqueue_event(
            session,
            EventName.MEETING_PREP_PACKET_GENERATED,
            "meeting_prep_packet",
            record.id,
            meeting_prep_packet_to_api(record),
            f"meeting.prep_packet_generated:{record.id}",
        )
        return await _meeting_to_model_with_children(session, meeting)


async def record_meeting_outcome(
    meeting_id: str,
    request: MeetingOutcomeRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
    crm_client: CrmClient | None = None,
) -> MeetingHandoffOut | None:
    resolved = settings or get_settings()
    async with session_scope(resolved) as session:
        meeting = await session.get(MeetingHandoff, meeting_id)
        if meeting is None:
            return None
        outcome_event_key = f"meeting.outcome_recorded:{meeting.id}:{idempotency_key}"
        existing_outcome_event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.idempotency_key == outcome_event_key)
        )
        if existing_outcome_event is not None:
            return await _meeting_to_model_with_children(session, meeting)
        meeting.status = (
            "scheduled" if request.outcome_status.value == "rescheduled" else "completed"
        )
        meeting.outcome_status = request.outcome_status.value
        meeting.outcome_notes = request.outcome_notes
        meeting.next_steps = list(request.next_steps)
        meeting.updated_at = utcnow()
        meeting.version += 1
        tasks = await _create_follow_up_tasks(session, meeting, request.follow_up_tasks)
        _enqueue_event(
            session,
            EventName.MEETING_OUTCOME_RECORDED,
            "meeting_handoff",
            meeting.id,
            meeting_to_api(meeting),
            outcome_event_key,
        )
        for task in tasks:
            _enqueue_event(
                session,
                EventName.MEETING_FOLLOW_UP_TASK_CREATED,
                "meeting_follow_up_task",
                task.id,
                meeting_follow_up_task_to_api(task),
                f"meeting.follow_up_task_created:{task.id}",
            )
        await _sync_meeting_to_crm(
            session,
            meeting,
            actor=actor,
            settings=resolved,
            client=crm_client,
        )
        return await _meeting_to_model_with_children(session, meeting)


async def retry_meeting_crm_sync(
    meeting_id: str,
    *,
    actor: str,
    settings: Settings | None = None,
    crm_client: CrmClient | None = None,
) -> MeetingHandoffOut | None:
    resolved = settings or get_settings()
    async with session_scope(resolved) as session:
        meeting = await session.get(MeetingHandoff, meeting_id)
        if meeting is None:
            return None
        await _sync_meeting_to_crm(
            session,
            meeting,
            actor=actor,
            settings=resolved,
            client=crm_client,
        )
        return await _meeting_to_model_with_children(session, meeting)


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
    calendars = await client.get_availability(
        attendees=[str(attendee).lower() for attendee in request.attendees],
        time_min=request.time_min,
        time_max=request.time_max,
        timezone=request.timezone,
    )
    return CalendarAvailabilityResult(calendars=calendars, provider=client.provider)


def meeting_to_api(meeting: MeetingHandoff) -> dict[str, object]:
    return {
        "id": meeting.id,
        "crm_target_id": meeting.crm_target_id,
        "sequence_enrollment_id": meeting.sequence_enrollment_id,
        "account_id": meeting.account_id,
        "contact_id": meeting.contact_id,
        "status": meeting.status,
        "subject": meeting.subject,
        "description": meeting.description,
        "location": meeting.location,
        "start_at": meeting.start_at,
        "end_at": meeting.end_at,
        "timezone": meeting.timezone,
        "attendees": meeting.attendees or [],
        "calendar_provider": meeting.calendar_provider,
        "calendar_id": meeting.calendar_id,
        "provider_event_id": meeting.provider_event_id,
        "provider_html_link": meeting.provider_html_link,
        "outcome_status": meeting.outcome_status,
        "outcome_notes": meeting.outcome_notes,
        "next_steps": meeting.next_steps or [],
        "crm_sync_status": meeting.crm_sync_status,
        "crm_sync_error": meeting.crm_sync_error,
        "crm_retry_after_seconds": meeting.crm_retry_after_seconds,
        "policy_snapshot": meeting.policy_snapshot or {},
        "version": meeting.version,
        "created_at": meeting.created_at,
        "updated_at": meeting.updated_at,
    }


def meeting_to_model(
    meeting: MeetingHandoff,
    *,
    prep_packet: MeetingPrepPacket | None = None,
    follow_up_tasks: list[MeetingFollowUpTask] | None = None,
) -> MeetingHandoffOut:
    payload = meeting_to_api(meeting)
    payload["prep_packet"] = (
        meeting_prep_packet_to_api(prep_packet) if prep_packet is not None else None
    )
    payload["follow_up_tasks"] = [
        meeting_follow_up_task_to_api(task) for task in follow_up_tasks or []
    ]
    return MeetingHandoffOut.model_validate(payload)


def meeting_prep_packet_to_api(packet: MeetingPrepPacket) -> dict[str, object]:
    return {
        "id": packet.id,
        "meeting_id": packet.meeting_id,
        "account_summary": packet.account_summary,
        "stakeholder_map": packet.stakeholder_map or [],
        "likely_security_priorities": packet.likely_security_priorities or [],
        "suggested_questions": packet.suggested_questions or [],
        "risks": packet.risks or [],
        "source_snapshot": packet.source_snapshot or {},
        "generated_by": packet.generated_by,
        "created_at": packet.created_at,
        "updated_at": packet.updated_at,
    }


def meeting_prep_packet_to_model(packet: MeetingPrepPacket) -> MeetingPrepPacketOut:
    return MeetingPrepPacketOut.model_validate(meeting_prep_packet_to_api(packet))


def meeting_follow_up_task_to_api(task: MeetingFollowUpTask) -> dict[str, object]:
    return {
        "id": task.id,
        "meeting_id": task.meeting_id,
        "title": task.title,
        "description": task.description,
        "owner": task.owner,
        "due_at": task.due_at,
        "status": task.status,
        "crm_sync_status": task.crm_sync_status,
        "provider_task_id": task.provider_task_id,
        "last_error": task.last_error,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def meeting_follow_up_task_to_model(task: MeetingFollowUpTask) -> MeetingFollowUpTaskOut:
    return MeetingFollowUpTaskOut.model_validate(meeting_follow_up_task_to_api(task))


async def _meeting_to_model_with_children(
    session: Any,
    meeting: MeetingHandoff,
) -> MeetingHandoffOut:
    packet = await _latest_prep_packet(session, meeting.id)
    result = await session.execute(
        select(MeetingFollowUpTask)
        .where(MeetingFollowUpTask.meeting_id == meeting.id)
        .order_by(MeetingFollowUpTask.created_at.asc(), MeetingFollowUpTask.id.asc())
    )
    return meeting_to_model(
        meeting,
        prep_packet=packet,
        follow_up_tasks=list(result.scalars()),
    )


async def _latest_prep_packet(session: Any, meeting_id: str) -> MeetingPrepPacket | None:
    return await session.scalar(
        select(MeetingPrepPacket)
        .where(MeetingPrepPacket.meeting_id == meeting_id)
        .order_by(MeetingPrepPacket.created_at.desc(), MeetingPrepPacket.id.desc())
        .limit(1)
    )


async def _prep_request_for_meeting(
    session: Any,
    meeting: MeetingHandoff,
) -> tuple[PrepPacketRequest, dict[str, object]]:
    account = await session.get(Account, meeting.account_id) if meeting.account_id else None
    contact = await session.get(Contact, meeting.contact_id) if meeting.contact_id else None
    if account is None and contact and contact.account_id:
        account = await session.get(Account, contact.account_id)

    contacts = []
    if account is not None:
        result = await session.execute(
            select(Contact).where(Contact.account_id == account.id).order_by(Contact.full_name)
        )
        contacts = list(result.scalars())
    elif contact is not None:
        contacts = [contact]

    signals = []
    if account is not None:
        result = await session.execute(
            select(Signal)
            .where(Signal.account_id == account.id)
            .order_by(Signal.signal_timestamp.desc())
            .limit(25)
        )
        signals = list(result.scalars())

    target = await session.get(CrmTarget, meeting.crm_target_id) if meeting.crm_target_id else None
    account_payload = (
        {
            "id": account.id,
            "company_name": account.company_name,
            "domain": account.domain,
            "industry": account.industry,
            "security_stack": account.security_stack or {},
        }
        if account is not None
        else {"company_name": "Account"}
    )
    contact_payloads = [
        {
            "id": item.id,
            "full_name": item.full_name,
            "title": item.title,
            "email": item.email,
            "persona_type": item.persona_type,
            "buying_role": item.buying_role,
        }
        for item in contacts
    ]
    signal_payloads = [
        {
            "id": item.id,
            "signal_type": item.signal_type,
            "signal_topic": item.signal_topic,
            "signal_strength": item.signal_strength,
            "product_relevance": item.product_relevance,
            "recommended_play": item.recommended_play,
        }
        for item in signals
    ]
    signal_payloads.extend(await _target_signals(session, target))
    source_snapshot = {
        "account_id": account.id if account else None,
        "contact_ids": [item.id for item in contacts],
        "signal_ids": [item.id for item in signals],
        "crm_target_id": meeting.crm_target_id,
        "crm_target_type": target.target_type if target else None,
        "crm_target_target_id": target.target_id if target else None,
    }
    return (
        PrepPacketRequest(
            account=account_payload,
            contacts=contact_payloads,
            signals=signal_payloads,
            meeting_time=meeting.start_at,
        ),
        source_snapshot,
    )


async def _target_signals(session: Any, target: CrmTarget | None) -> list[dict[str, object]]:
    if target is None:
        return []
    if target.target_type in {"security_incident", "incident"}:
        incident = await session.get(SecurityIncident, target.target_id)
        if incident is None:
            return []
        return [
            {
                "signal_type": "security_incident",
                "signal_topic": incident.title,
                "signal_strength": incident.confidence,
                "product_relevance": incident.attack_vector,
            }
        ]
    if target.target_type in {"cyber_event", "event"}:
        event = await session.get(CyberEvent, target.target_id)
        if event is None:
            return []
        return [
            {
                "signal_type": "cyber_event",
                "signal_topic": event.name,
                "signal_strength": event.confidence,
                "product_relevance": ", ".join(str(topic) for topic in event.topics or []),
            }
        ]
    return []


async def _create_follow_up_tasks(
    session: Any,
    meeting: MeetingHandoff,
    requests: list[MeetingFollowUpTaskCreate],
) -> list[MeetingFollowUpTask]:
    now = utcnow()
    tasks = []
    for index, request in enumerate(requests, start=1):
        key = f"meeting-follow-up:{meeting.id}:{index}:{request.title.lower()}"
        existing = await session.scalar(
            select(MeetingFollowUpTask).where(MeetingFollowUpTask.idempotency_key == key)
        )
        if existing is not None:
            tasks.append(existing)
            continue
        task = MeetingFollowUpTask(
            meeting_id=meeting.id,
            title=request.title,
            description=request.description,
            owner=request.owner,
            due_at=request.due_at,
            status="open",
            crm_sync_status="pending",
            idempotency_key=key,
            created_at=now,
            updated_at=now,
        )
        session.add(task)
        tasks.append(task)
    await session.flush()
    return tasks


async def _sync_meeting_to_crm(
    session: Any,
    meeting: MeetingHandoff,
    *,
    actor: str,
    settings: Settings,
    client: CrmClient | None,
) -> None:
    tasks = list(
        (
            await session.execute(
                select(MeetingFollowUpTask)
                .where(MeetingFollowUpTask.meeting_id == meeting.id)
                .order_by(MeetingFollowUpTask.created_at.asc())
            )
        ).scalars()
    )
    plan = _crm_sync_plan(meeting, tasks, actor=actor, settings=settings)
    meeting.crm_sync_status = "pending"
    meeting.crm_sync_error = None
    meeting.crm_retry_after_seconds = None
    for task in tasks:
        task.crm_sync_status = "pending"
        task.last_error = None
        task.updated_at = utcnow()
    try:
        crm = client or AttioCrmClient(settings)
        result = await crm.sync(plan)
    except (CrmProviderError, ValueError) as exc:
        retryable = isinstance(exc, CrmProviderError) and exc.retryable
        meeting.crm_sync_status = "failed_retryable" if retryable else "failed_terminal"
        meeting.crm_sync_error = str(exc)
        meeting.crm_retry_after_seconds = (
            exc.retry_after_seconds if isinstance(exc, CrmProviderError) else None
        )
        meeting.status = "failed_sync" if retryable else meeting.status
        meeting.updated_at = utcnow()
        for task in tasks:
            task.crm_sync_status = meeting.crm_sync_status
            task.last_error = str(exc)
            task.updated_at = utcnow()
        return

    meeting.crm_sync_status = "succeeded"
    meeting.crm_sync_error = None
    meeting.crm_retry_after_seconds = None
    meeting.updated_at = utcnow()
    for task in tasks:
        task.crm_sync_status = "succeeded"
        task.provider_task_id = result.provider_record_id
        task.last_error = None
        task.updated_at = utcnow()
    _enqueue_event(
        session,
        EventName.CRM_SYNCED,
        "meeting_handoff",
        meeting.id,
        {
            "meeting_id": meeting.id,
            "provider_record_id": result.provider_record_id,
            "provider_list_entry_id": result.provider_list_entry_id,
            "raw_response": result.raw_response,
        },
        f"crm.synced:meeting:{meeting.id}:{meeting.version}",
        source_service="crm-service",
    )


def _crm_sync_plan(
    meeting: MeetingHandoff,
    tasks: list[MeetingFollowUpTask],
    *,
    actor: str,
    settings: Settings,
) -> CrmSyncPlan:
    return CrmSyncPlan(
        sync_type="meeting_handoff",
        target_id=meeting.id,
        provider_object="meeting_handoffs",
        stable_match_key=f"ghostrecon_meeting:{meeting.id}",
        matching_attribute="ghostrecon_id",
        values={
            "ghostrecon_id": meeting.id,
            "crm_target_id": meeting.crm_target_id,
            "account_id": meeting.account_id,
            "contact_id": meeting.contact_id,
            "subject": meeting.subject,
            "status": meeting.status,
            "start_at": _iso(meeting.start_at),
            "end_at": _iso(meeting.end_at),
            "timezone": meeting.timezone,
            "outcome_status": meeting.outcome_status,
            "outcome_notes": meeting.outcome_notes,
            "next_steps": meeting.next_steps or [],
            "calendar_provider": meeting.calendar_provider,
            "calendar_event_id": meeting.provider_event_id,
            "calendar_link": meeting.provider_html_link,
            "follow_up_tasks": [meeting_follow_up_task_to_api(task) for task in tasks],
            "synced_by": actor,
        },
        list_api_slug=settings.attio_meetings_list_api_slug,
        list_entry_values={
            "meeting_status": meeting.status,
            "outcome_status": meeting.outcome_status,
        },
    )


async def _contact_for_meeting(
    session: Any,
    target: CrmTarget | None,
    requested_contact_id: str | None,
) -> Contact | None:
    if requested_contact_id:
        contact = await session.get(Contact, requested_contact_id)
        if contact is None:
            raise ValueError("contact not found")
        return contact
    if target is None:
        return None
    if target.target_type in {"contact", "incident_contact"}:
        return await session.get(Contact, target.target_id)
    if target.target_type == "email_candidate":
        candidate = await session.get(EmailCandidateRecord, target.target_id)
        if candidate and candidate.contact_id:
            return await session.get(Contact, candidate.contact_id)
    return None


def _meeting_attendees(
    requested: list[MeetingAttendee],
    contact: Contact | None,
) -> list[MeetingAttendee]:
    attendees = list(requested)
    seen = {str(attendee.email).lower() for attendee in attendees}
    if contact and contact.email and contact.email.lower() not in seen:
        attendees.append(
            MeetingAttendee(
                email=contact.email.lower(),
                name=contact.full_name,
                optional=False,
            )
        )
    if not attendees:
        raise ValueError("meeting requires at least one attendee")
    return attendees


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


def _require_exported_target(target: CrmTarget | None) -> None:
    if target is None:
        raise ValueError("crm target not found")
    if target.status != "exported" or target.export_status != "exported":
        raise ValueError("crm target must be exported before meeting handoff")


def _require_time_window(start_at: datetime, end_at: datetime) -> None:
    if end_at <= start_at:
        raise ValueError("end_at must be after start_at")


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


def utcnow() -> datetime:
    return datetime.now(UTC)
