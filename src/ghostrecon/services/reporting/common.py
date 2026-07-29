from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import String, cast

from ghostrecon.common.config import Settings
from ghostrecon.models.api import (
    ReportingMetadata,
    SourceHealth,
    SourceHealthStatus,
)
from ghostrecon.services.source_registry import list_source_health

PROJECTION_VERSION = "reporting.v1.query"


STALE_SOURCE_STATUSES = {
    SourceHealthStatus.STALE,
    SourceHealthStatus.DEGRADED,
    SourceHealthStatus.UNKNOWN,
}


def _like(value: str | None) -> str | None:
    text = str(value or "").strip()
    return f"%{text}%" if text else None


def _fuzzy(column: Any, value: str | None) -> Any:
    return cast(column, String).ilike(_like(value) or "")


def _text_matches(value: object, needle: str | None) -> bool:
    text = str(needle or "").strip().lower()
    if not text:
        return True
    return text in str(value or "").lower()


KPI_CATALOG = {
    "discovery_coverage": [
        "events_by_geography",
        "incidents_by_language",
        "source_topic_coverage",
    ],
    "source_freshness": [
        "fetch_success_rate",
        "parse_yield",
        "duplicate_rate",
        "projection_lag_seconds",
    ],
    "event_participants": [
        "participants_by_reuse_state",
        "participant_policy_block_rate",
    ],
    "incident_quality": [
        "incident_candidates",
        "corroboration_time_seconds",
        "false_positive_rate",
        "watchlist_follow_on_coverage",
    ],
    "review": [
        "review_age_seconds",
        "review_sla_breaches",
        "approval_rate",
        "bulk_conflict_rate",
        "policy_block_rate",
    ],
    "crm_readiness": [
        "approved_crm_targets",
        "targets_not_exported",
        "targets_blocked_by_policy",
    ],
    "meeting_handoff": [
        "meetings_booked",
        "prep_packet_latency_seconds",
        "meeting_outcome_rate",
        "meeting_crm_sync_failures",
        "follow_up_task_completion_rate",
    ],
}


def reporting_metadata_from_sources(
    sources: list[SourceHealth],
    *,
    generated_at: datetime | None = None,
    record_watermark_name: str | None = None,
    record_watermark: datetime | None = None,
) -> ReportingMetadata:
    generated = generated_at or datetime.now(UTC)
    latest_success = _latest_datetime(source.last_success_at for source in sources)
    degraded = [
        source.name for source in sources if source.freshness_status in STALE_SOURCE_STATUSES
    ]
    watermarks: dict[str, object] = {"projection_generated_at": generated}
    if latest_success is not None:
        watermarks["source_last_success_at"] = latest_success
    if record_watermark_name and record_watermark is not None:
        watermarks[record_watermark_name] = record_watermark
    return ReportingMetadata(
        generated_at=generated,
        watermarks=watermarks,
        projection_version=PROJECTION_VERSION,
        stale=bool(degraded),
        degraded_dependencies=degraded,
    )


async def reporting_metadata(
    kind: str | None = None,
    *,
    settings: Settings | None = None,
    record_watermark_name: str | None = None,
    record_watermark: datetime | None = None,
) -> ReportingMetadata:
    sources = await list_source_health(kind, settings)
    return reporting_metadata_from_sources(
        sources,
        record_watermark_name=record_watermark_name,
        record_watermark=record_watermark,
    )


def parse_cursor(cursor: str | None) -> int:
    if cursor is None or cursor == "":
        return 0
    try:
        offset = int(cursor)
    except ValueError as exc:
        raise ValueError("cursor must be a non-negative integer offset") from exc
    if offset < 0:
        raise ValueError("cursor must be a non-negative integer offset")
    return offset


def next_cursor(rows: list[Any], limit: int, offset: int) -> str | None:
    if len(rows) <= limit:
        return None
    return str(offset + limit)


from .crm import _latest_datetime  # noqa: E402
