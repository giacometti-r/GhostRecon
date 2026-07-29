from __future__ import annotations

from ghostrecon.common.config import Settings
from ghostrecon.models.api import (
    ReportingOperatorContext,
    ReportingSourceHealthList,
)
from ghostrecon.services.source_registry import list_source_health


async def get_reporting_source_health(
    *,
    kind: str | None = None,
    freshness_status: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingSourceHealthList:
    context = operator or ReportingOperatorContext()
    offset = parse_cursor(cursor)
    sources = await list_source_health(kind, settings)
    if kind:
        sources = [source for source in sources if _text_matches(source.source_kind, kind)]
    if freshness_status:
        sources = [
            source
            for source in sources
            if _text_matches(source.freshness_status.value, freshness_status)
            or _text_matches(source.name, freshness_status)
        ]
    sources = sorted(sources, key=lambda source: (source.source_kind, source.name))
    rows = sources[offset : offset + limit + 1]
    page = rows[:limit]
    metadata = reporting_metadata_from_sources(
        sources,
        record_watermark_name="source_last_success_at",
        record_watermark=_latest_datetime(source.last_success_at for source in sources),
    )
    return ReportingSourceHealthList(
        metadata=metadata,
        sources=[project_source_health(source, context) for source in page],
        next_cursor=next_cursor(rows, limit, offset),
    )


from .common import (  # noqa: E402
    _text_matches,
    next_cursor,
    parse_cursor,
    reporting_metadata_from_sources,
)
from .crm import _latest_datetime  # noqa: E402
from .kpis import project_source_health  # noqa: E402
