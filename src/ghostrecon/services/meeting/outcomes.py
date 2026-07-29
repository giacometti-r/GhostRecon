from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName
from ghostrecon.models.api import (
    MeetingFollowUpTaskCreate,
    MeetingHandoffOut,
    MeetingOutcomeRequest,
)
from ghostrecon.models.db import (
    MeetingFollowUpTask,
    MeetingHandoff,
    OutboxEvent,
)
from ghostrecon.services.crm_attio import (
    CrmClient,
)


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


from .common import utcnow  # noqa: E402
from .crm_sync import _sync_meeting_to_crm  # noqa: E402
from .events import _enqueue_event  # noqa: E402
from .serializers import (  # noqa: E402
    _meeting_to_model_with_children,
    meeting_follow_up_task_to_api,
    meeting_to_api,
)
