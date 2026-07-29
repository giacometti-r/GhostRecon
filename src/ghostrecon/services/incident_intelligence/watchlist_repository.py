from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select

from ghostrecon.common.config import Settings
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    WatchTargetCreate,
    WatchTargetPatch,
)
from ghostrecon.models.db import (
    WatchTarget,
    WatchTargetMonitoringRun,
)
from ghostrecon.services.search_adapters import (
    watch_monitoring_queries,
)


class WatchlistRepositoryMixin:
    async def list_watch_targets(
        self, *, target_type: str | None, enabled: bool | None, limit: int
    ) -> list[WatchTarget]:
        stmt = select(WatchTarget).order_by(WatchTarget.created_at.desc()).limit(limit)
        if target_type:
            stmt = stmt.where(WatchTarget.target_type == target_type)
        if enabled is not None:
            stmt = stmt.where(WatchTarget.enabled == enabled)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def create_watch_target(
        self, payload: WatchTargetCreate, actor: str, idempotency_key: str
    ) -> WatchTarget:
        key = _watch_target_key(payload.target_type, payload.canonical_target_key)
        existing = await self.session.scalar(
            select(WatchTarget).where(
                WatchTarget.target_type == payload.target_type,
                WatchTarget.canonical_target_key == key,
            )
        )
        if existing is not None:
            return existing
        target = WatchTarget(
            target_type=payload.target_type,
            canonical_target_key=key,
            display_name=payload.display_name,
            query_config=payload.query_config,
            enabled=True,
            owner=payload.owner,
            origin_incident_id=payload.origin_incident_id,
            created_by=actor,
            monitoring_status="queued" if payload.target_type == "company" else "not_required",
            next_monitoring_at=datetime.now(UTC) if payload.target_type == "company" else None,
            monitoring_summary={},
        )
        self.session.add(target)
        await self.session.flush()
        self._audit(actor, "watch_target.created", "watch_target", target.id, idempotency_key)
        self._enqueue_event(
            new_event(
                event_name=EventName.WATCH_TARGET_CREATED,
                aggregate_type="watch_target",
                aggregate_id=target.id,
                source_service=INCIDENT_SERVICE_NAME,
                payload={
                    "watch_target_id": target.id,
                    "target_type": target.target_type,
                    "canonical_target_key": target.canonical_target_key,
                    "origin_incident_id": target.origin_incident_id,
                },
                idempotency_key=f"watch_target.created:{target.id}",
            )
        )
        return target

    async def patch_watch_target(
        self, watch_target_id: str, payload: WatchTargetPatch, actor: str, idempotency_key: str
    ) -> WatchTarget | None:
        target = await self.session.get(WatchTarget, watch_target_id)
        if target is None:
            return None
        if target.version != payload.version:
            raise ValueError("watch target version conflict")
        if payload.enabled is not None:
            target.enabled = payload.enabled
            if payload.enabled and target.target_type == "company":
                target.monitoring_status = "queued"
                target.monitoring_error = None
                target.next_monitoring_at = datetime.now(UTC)
            elif not payload.enabled:
                target.monitoring_status = "paused"
                target.next_monitoring_at = None
        if payload.display_name is not None:
            target.display_name = payload.display_name
        if payload.query_config is not None:
            target.query_config = payload.query_config
        if payload.owner is not None:
            target.owner = payload.owner
        target.version += 1
        self._audit(actor, "watch_target.updated", "watch_target", target.id, idempotency_key)
        return target

    async def list_due_monitoring_targets(self, now: datetime) -> list[WatchTarget]:
        result = await self.session.execute(
            select(WatchTarget)
            .where(WatchTarget.target_type == "company")
            .where(WatchTarget.enabled.is_(True))
            .where(
                or_(
                    WatchTarget.next_monitoring_at.is_(None),
                    WatchTarget.next_monitoring_at <= now,
                )
            )
            .order_by(WatchTarget.next_monitoring_at.asc().nullsfirst(), WatchTarget.id.asc())
            .limit(100)
        )
        return list(result.scalars())

    async def monitor_watch_target(
        self,
        target: WatchTarget,
        *,
        provider: Any,
        settings: Settings,
    ) -> WatchTargetMonitoringRun:
        started_at = datetime.now(UTC)
        queries = watch_monitoring_queries(target.display_name)
        results_by_query: list[dict[str, object]] = []
        top_results: list[dict[str, object]] = []
        for query in queries:
            results = await provider.search_news(query, limit=settings.search_result_limit)
            rows = [
                {
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                    "source": result.source,
                    "published_at": result.published_at,
                    "rank": result.rank,
                }
                for result in results
            ]
            results_by_query.append({"query": query, "result_count": len(rows), "results": rows})
            top_results.extend(rows[:2])

        completed_at = datetime.now(UTC)
        status = "not_configured" if provider.provider_name == "disabled" else "completed"
        result_count = sum(int(item["result_count"]) for item in results_by_query)
        summary = {
            "provider": provider.provider_name,
            "result_count": result_count,
            "queries": results_by_query,
            "top_results": top_results[:5],
        }
        run = WatchTargetMonitoringRun(
            watch_target_id=target.id,
            provider=provider.provider_name,
            status=status,
            query_summary={"queries": queries},
            result_summary=summary,
            error=None,
            started_at=started_at,
            completed_at=completed_at,
        )
        self.session.add(run)
        target.monitoring_status = status
        target.last_monitored_at = completed_at
        target.next_monitoring_at = completed_at + timedelta(
            seconds=settings.watch_monitoring_interval_seconds
        )
        target.monitoring_error = None
        target.monitoring_summary = summary
        target.version += 1
        await self.session.flush()
        return run

    async def record_monitoring_failure(
        self, target: WatchTarget, provider_name: str, error: str
    ) -> WatchTargetMonitoringRun:
        now = datetime.now(UTC)
        run = WatchTargetMonitoringRun(
            watch_target_id=target.id,
            provider=provider_name,
            status="failed",
            query_summary={"queries": watch_monitoring_queries(target.display_name)},
            result_summary={},
            error=error[:1000],
            started_at=now,
            completed_at=now,
        )
        self.session.add(run)
        target.monitoring_status = "failed"
        target.last_monitored_at = now
        target.next_monitoring_at = now + timedelta(hours=1)
        target.monitoring_error = error[:1000]
        target.monitoring_summary = {}
        target.version += 1
        await self.session.flush()
        return run


from .candidates import INCIDENT_SERVICE_NAME  # noqa: E402
from .parsers import _watch_target_key  # noqa: E402
