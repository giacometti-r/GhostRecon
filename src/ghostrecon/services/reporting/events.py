from __future__ import annotations

from sqlalchemy import or_, select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    CyberEventOut,
    ReportingEventDetail,
    ReportingEventList,
    ReportingOperatorContext,
    normalize_event_format_value,
)
from ghostrecon.models.db import (
    CyberEvent,
)
from ghostrecon.services.event_intelligence import event_to_api


async def get_reporting_events(
    *,
    series: str | None = None,
    source: str | None = None,
    country: str | None = None,
    event_format: str | None = None,
    topic: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingEventList:
    _ = operator
    offset = parse_cursor(cursor)
    async with session_scope(settings) as session:
        stmt = select(CyberEvent).order_by(
            CyberEvent.starts_at_utc.asc().nullslast(),
            CyberEvent.name.asc(),
            CyberEvent.id.asc(),
        )
        if series:
            stmt = stmt.where(
                or_(
                    _fuzzy(CyberEvent.event_series_key, series),
                    _fuzzy(CyberEvent.name, series),
                )
            )
        if source:
            stmt = stmt.where(_fuzzy(CyberEvent.source_definition_id, source))
        if country:
            stmt = stmt.where(_fuzzy(CyberEvent.country, country))
        if event_format:
            try:
                normalized_format = str(normalize_event_format_value(event_format))
            except ValueError:
                normalized_format = event_format
            stmt = stmt.where(_fuzzy(CyberEvent.event_format, normalized_format))
        if topic:
            stmt = stmt.where(_fuzzy(CyberEvent.topics, topic))
        result = await session.execute(stmt.offset(offset).limit(limit + 1))
        rows = list(result.scalars())

    events = rows[:limit]
    metadata = await reporting_metadata(
        "event",
        settings=settings,
        record_watermark_name="event_updated_at",
        record_watermark=_latest_datetime(event.updated_at for event in events),
    )
    return ReportingEventList(
        metadata=metadata,
        events=[CyberEventOut.model_validate(event_to_api(event)) for event in events],
        next_cursor=next_cursor(rows, limit, offset),
    )


async def get_reporting_event_detail(
    event_id: str,
    *,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingEventDetail | None:
    _ = operator
    async with session_scope(settings) as session:
        event = await session.get(CyberEvent, event_id)
    if event is None:
        return None
    metadata = await reporting_metadata(
        "event",
        settings=settings,
        record_watermark_name="event_updated_at",
        record_watermark=event.updated_at,
    )
    return ReportingEventDetail(
        metadata=metadata,
        event=CyberEventOut.model_validate(event_to_api(event)),
    )


from .common import _fuzzy, next_cursor, parse_cursor, reporting_metadata  # noqa: E402
from .crm import _latest_datetime  # noqa: E402
