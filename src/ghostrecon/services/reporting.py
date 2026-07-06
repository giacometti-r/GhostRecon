from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    CrmTargetOut,
    CyberEventOut,
    DashboardRole,
    ReportingCrmTargetList,
    ReportingEventDetail,
    ReportingEventList,
    ReportingIncidentDetail,
    ReportingIncidentList,
    ReportingKpiCatalog,
    ReportingMetadata,
    ReportingOperatorContext,
    ReportingReviewQueue,
    ReportingSourceHealthList,
    ReportingWatchTargetList,
    ReviewCandidateOut,
    SecurityIncidentOut,
    SourceHealth,
    SourceHealthStatus,
    WatchTargetOut,
)
from ghostrecon.models.db import (
    CrmTarget,
    CyberEvent,
    ReviewCandidate,
    SecurityIncident,
    WatchTarget,
)
from ghostrecon.services.enrichment_workflows import review_candidate_to_api
from ghostrecon.services.event_intelligence import event_to_api
from ghostrecon.services.governance import crm_target_to_api
from ghostrecon.services.incident_intelligence import incident_to_api, watch_target_to_api
from ghostrecon.services.source_registry import list_source_health

PROJECTION_VERSION = "reporting.v1.query"
STALE_SOURCE_STATUSES = {
    SourceHealthStatus.STALE,
    SourceHealthStatus.DEGRADED,
    SourceHealthStatus.UNKNOWN,
}

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
        source.name
        for source in sources
        if source.freshness_status in STALE_SOURCE_STATUSES
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
            stmt = stmt.where(CyberEvent.event_series_key == series)
        if source:
            stmt = stmt.where(CyberEvent.source_definition_id == source)
        if country:
            stmt = stmt.where(CyberEvent.country == country.upper())
        if event_format:
            stmt = stmt.where(CyberEvent.event_format == event_format)
        if topic:
            stmt = stmt.where(CyberEvent.topics.contains([topic]))
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


async def get_reporting_incidents(
    *,
    status: str | None = None,
    source: str | None = None,
    company: str | None = None,
    attack_vector: str | None = None,
    incident_type: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingIncidentList:
    _ = operator
    offset = parse_cursor(cursor)
    async with session_scope(settings) as session:
        stmt = select(SecurityIncident).order_by(
            SecurityIncident.created_at.desc(),
            SecurityIncident.id.asc(),
        )
        if status:
            stmt = stmt.where(SecurityIncident.status == status)
        if source:
            stmt = stmt.where(SecurityIncident.source_definition_id == source)
        if company:
            stmt = stmt.where(SecurityIncident.affected_companies.contains([company]))
        if attack_vector:
            stmt = stmt.where(SecurityIncident.attack_vector == attack_vector)
        if incident_type:
            stmt = stmt.where(SecurityIncident.incident_type == incident_type)
        result = await session.execute(stmt.offset(offset).limit(limit + 1))
        rows = list(result.scalars())

    incidents = rows[:limit]
    metadata = await reporting_metadata(
        "incident",
        settings=settings,
        record_watermark_name="incident_updated_at",
        record_watermark=_latest_datetime(incident.updated_at for incident in incidents),
    )
    return ReportingIncidentList(
        metadata=metadata,
        incidents=[
            SecurityIncidentOut.model_validate(incident_to_api(incident))
            for incident in incidents
        ],
        next_cursor=next_cursor(rows, limit, offset),
    )


async def get_reporting_incident_detail(
    incident_id: str,
    *,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingIncidentDetail | None:
    _ = operator
    async with session_scope(settings) as session:
        incident = await session.get(SecurityIncident, incident_id)
    if incident is None:
        return None
    metadata = await reporting_metadata(
        "incident",
        settings=settings,
        record_watermark_name="incident_updated_at",
        record_watermark=incident.updated_at,
    )
    return ReportingIncidentDetail(
        metadata=metadata,
        incident=SecurityIncidentOut.model_validate(incident_to_api(incident)),
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
    _ = operator
    offset = parse_cursor(cursor)
    async with session_scope(settings) as session:
        stmt = select(WatchTarget).order_by(WatchTarget.created_at.desc(), WatchTarget.id.asc())
        if target_type:
            stmt = stmt.where(WatchTarget.target_type == target_type)
        if enabled is not None:
            stmt = stmt.where(WatchTarget.enabled == enabled)
        if owner:
            stmt = stmt.where(WatchTarget.owner == owner)
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
        watch_targets=[
            WatchTargetOut.model_validate(watch_target_to_api(target))
            for target in targets
        ],
        next_cursor=next_cursor(rows, limit, offset),
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
            stmt = stmt.where(ReviewCandidate.status == status)
        if candidate_type:
            stmt = stmt.where(ReviewCandidate.candidate_type == candidate_type)
        if target_type:
            stmt = stmt.where(ReviewCandidate.target_type == target_type)
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


async def get_reporting_crm_targets(
    *,
    status: str | None = None,
    target_type: str | None = None,
    export_status: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingCrmTargetList:
    context = operator or ReportingOperatorContext()
    offset = parse_cursor(cursor)
    async with session_scope(settings) as session:
        stmt = select(CrmTarget).order_by(CrmTarget.created_at.desc(), CrmTarget.id.asc())
        if status:
            stmt = stmt.where(CrmTarget.status == status)
        if target_type:
            stmt = stmt.where(CrmTarget.target_type == target_type)
        if export_status:
            stmt = stmt.where(CrmTarget.export_status == export_status)
        result = await session.execute(stmt.offset(offset).limit(limit + 1))
        rows = list(result.scalars())

    targets = rows[:limit]
    metadata = await reporting_metadata(
        None,
        settings=settings,
        record_watermark_name="crm_target_updated_at",
        record_watermark=_latest_datetime(target.updated_at for target in targets),
    )
    return ReportingCrmTargetList(
        metadata=metadata,
        crm_targets=[project_crm_target(target, context) for target in targets],
        next_cursor=next_cursor(rows, limit, offset),
    )


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
    if freshness_status:
        sources = [
            source
            for source in sources
            if source.freshness_status.value == freshness_status
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


async def get_reporting_kpi_catalog(
    *,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingKpiCatalog:
    _ = operator
    metadata = await reporting_metadata(None, settings=settings)
    return ReportingKpiCatalog(metadata=metadata, kpis=KPI_CATALOG)


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


def project_review_candidate(
    candidate: ReviewCandidate,
    context: ReportingOperatorContext,
) -> ReviewCandidateOut:
    payload = review_candidate_to_api(candidate)
    if context.role == DashboardRole.VIEWER:
        payload["reason"] = None
        payload["evidence_summary"] = {}
        payload["policy_snapshot"] = {}
        payload["policy_snapshot_hash"] = None
    return ReviewCandidateOut.model_validate(payload)


def project_crm_target(
    target: CrmTarget,
    context: ReportingOperatorContext,
) -> CrmTargetOut:
    payload = crm_target_to_api(target)
    if context.role == DashboardRole.VIEWER:
        payload["policy_snapshot"] = {}
        payload["approval_snapshot"] = {}
    return CrmTargetOut.model_validate(payload)


def project_source_health(
    source: SourceHealth,
    context: ReportingOperatorContext,
) -> SourceHealth:
    if context.role in {DashboardRole.GOVERNANCE_REVIEWER, DashboardRole.ADMINISTRATOR}:
        return source
    return source.model_copy(update={"checkpoint_state": {}, "last_error": None})


def _latest_datetime(values: Any) -> datetime | None:
    dates = [value for value in values if isinstance(value, datetime)]
    if not dates:
        return None
    return max(dates)
