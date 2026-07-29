from __future__ import annotations

from sqlalchemy import or_, select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    ReportingOperatorContext,
    ReportingWatchTargetDetail,
    ReportingWatchTargetList,
)
from ghostrecon.models.db import (
    WatchTarget,
)


async def get_reporting_watch_targets(
    *,
    target_type: str | None = None,
    enabled: bool | None = None,
    owner: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingWatchTargetList:
    context = operator or ReportingOperatorContext()
    offset = parse_cursor(cursor)
    async with session_scope(settings) as session:
        stmt = select(WatchTarget).order_by(WatchTarget.created_at.desc(), WatchTarget.id.asc())
        if target_type:
            stmt = stmt.where(_fuzzy(WatchTarget.target_type, target_type))
        else:
            stmt = stmt.where(WatchTarget.target_type == "company")
        if enabled is not None:
            stmt = stmt.where(WatchTarget.enabled == enabled)
        if owner:
            stmt = stmt.where(
                or_(
                    _fuzzy(WatchTarget.owner, owner),
                    _fuzzy(WatchTarget.display_name, owner),
                    _fuzzy(WatchTarget.canonical_target_key, owner),
                    _fuzzy(WatchTarget.monitoring_status, owner),
                )
            )
        result = await session.execute(stmt.offset(offset).limit(limit + 1))
        rows = list(result.scalars())

    targets = rows[:limit]
    metadata = await reporting_metadata(
        None,
        settings=settings,
        record_watermark_name="watch_target_updated_at",
        record_watermark=_latest_datetime(target.updated_at for target in targets),
    )
    return ReportingWatchTargetList(
        metadata=metadata,
        watch_targets=[project_watch_target(target, context) for target in targets],
        next_cursor=next_cursor(rows, limit, offset),
    )


async def get_reporting_watch_target_detail(
    watch_target_id: str,
    *,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingWatchTargetDetail | None:
    context = operator or ReportingOperatorContext()
    async with session_scope(settings) as session:
        target = await session.get(WatchTarget, watch_target_id)
    if target is None:
        return None
    metadata = await reporting_metadata(
        None,
        settings=settings,
        record_watermark_name="watch_target_updated_at",
        record_watermark=target.updated_at,
    )
    return ReportingWatchTargetDetail(
        metadata=metadata,
        watch_target=project_watch_target(target, context),
    )


from .common import _fuzzy, next_cursor, parse_cursor, reporting_metadata  # noqa: E402
from .crm import _latest_datetime, project_watch_target  # noqa: E402
