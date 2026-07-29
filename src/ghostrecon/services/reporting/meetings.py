from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    DashboardRole,
    MeetingHandoffOut,
    ReportingMeetingDetail,
    ReportingMeetingList,
    ReportingOperatorContext,
)
from ghostrecon.models.db import (
    MeetingFollowUpTask,
    MeetingHandoff,
    MeetingPrepPacket,
)
from ghostrecon.services.meeting import meeting_to_model


async def get_reporting_meetings(
    *,
    status: str | None = None,
    crm_sync_status: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingMeetingList:
    context = operator or ReportingOperatorContext()
    offset = parse_cursor(cursor)
    async with session_scope(settings) as session:
        stmt = select(MeetingHandoff).order_by(
            MeetingHandoff.start_at.desc(),
            MeetingHandoff.id.asc(),
        )
        if status:
            stmt = stmt.where(_fuzzy(MeetingHandoff.status, status))
        if crm_sync_status:
            stmt = stmt.where(_fuzzy(MeetingHandoff.crm_sync_status, crm_sync_status))
        result = await session.execute(stmt.offset(offset).limit(limit + 1))
        rows = list(result.scalars())
        meetings = [
            await _project_meeting_with_children(session, meeting, context)
            for meeting in rows[:limit]
        ]

    metadata = await reporting_metadata(
        None,
        settings=settings,
        record_watermark_name="meeting_updated_at",
        record_watermark=_latest_datetime(meeting.updated_at for meeting in rows[:limit]),
    )
    return ReportingMeetingList(
        metadata=metadata,
        meetings=meetings,
        next_cursor=next_cursor(rows, limit, offset),
    )


async def get_reporting_meeting_detail(
    meeting_id: str,
    *,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingMeetingDetail | None:
    context = operator or ReportingOperatorContext()
    async with session_scope(settings) as session:
        meeting = await session.get(MeetingHandoff, meeting_id)
        if meeting is None:
            return None
        projected = await _project_meeting_with_children(session, meeting, context)
    metadata = await reporting_metadata(
        None,
        settings=settings,
        record_watermark_name="meeting_updated_at",
        record_watermark=meeting.updated_at,
    )
    return ReportingMeetingDetail(metadata=metadata, meeting=projected)


async def _project_meeting_with_children(
    session: Any,
    meeting: MeetingHandoff,
    context: ReportingOperatorContext,
) -> MeetingHandoffOut:
    packet = await session.scalar(
        select(MeetingPrepPacket)
        .where(MeetingPrepPacket.meeting_id == meeting.id)
        .order_by(MeetingPrepPacket.created_at.desc(), MeetingPrepPacket.id.desc())
        .limit(1)
    )
    tasks = list(
        (
            await session.execute(
                select(MeetingFollowUpTask)
                .where(MeetingFollowUpTask.meeting_id == meeting.id)
                .order_by(MeetingFollowUpTask.created_at.asc(), MeetingFollowUpTask.id.asc())
            )
        ).scalars()
    )
    model = meeting_to_model(meeting, prep_packet=packet, follow_up_tasks=tasks)
    if context.role == DashboardRole.VIEWER:
        model = model.model_copy(update={"policy_snapshot": {}})
    return model


from .common import _fuzzy, next_cursor, parse_cursor, reporting_metadata  # noqa: E402
from .crm import _latest_datetime  # noqa: E402
