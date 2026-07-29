from __future__ import annotations

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    ReportingOperatorContext,
    ReportingReviewQueue,
)
from ghostrecon.models.db import (
    ReviewCandidate,
)


async def get_reporting_review_queue(
    *,
    status: str | None = "open",
    candidate_type: str | None = None,
    target_type: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingReviewQueue:
    context = operator or ReportingOperatorContext()
    offset = parse_cursor(cursor)
    async with session_scope(settings) as session:
        stmt = select(ReviewCandidate).order_by(
            ReviewCandidate.created_at.asc(),
            ReviewCandidate.id.asc(),
        )
        if status:
            stmt = stmt.where(_fuzzy(ReviewCandidate.status, status))
        if candidate_type:
            stmt = stmt.where(_fuzzy(ReviewCandidate.candidate_type, candidate_type))
        if target_type:
            stmt = stmt.where(_fuzzy(ReviewCandidate.target_type, target_type))
        result = await session.execute(stmt.offset(offset).limit(limit + 1))
        rows = list(result.scalars())

    candidates = rows[:limit]
    metadata = await reporting_metadata(
        None,
        settings=settings,
        record_watermark_name="review_queue_updated_at",
        record_watermark=_latest_datetime(candidate.updated_at for candidate in candidates),
    )
    return ReportingReviewQueue(
        metadata=metadata,
        candidates=[project_review_candidate(candidate, context) for candidate in candidates],
        next_cursor=next_cursor(rows, limit, offset),
    )


from .common import _fuzzy, next_cursor, parse_cursor, reporting_metadata  # noqa: E402
from .crm import _latest_datetime, project_review_candidate  # noqa: E402
