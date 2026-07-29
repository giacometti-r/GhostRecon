from __future__ import annotations

from datetime import UTC, datetime

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    WatchTargetCreate,
    WatchTargetPatch,
)
from ghostrecon.models.db import (
    SecurityIncident,
    WatchTarget,
)
from ghostrecon.services.search_adapters import (
    news_provider_for_settings,
)


async def list_watch_targets(
    *,
    target_type: str | None = None,
    enabled: bool | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> list[WatchTarget]:
    async with session_scope(settings) as session:
        repository = IncidentIntelligenceRepository(session)
        return await repository.list_watch_targets(
            target_type=target_type, enabled=enabled, limit=limit
        )


async def get_watch_target(
    watch_target_id: str,
    *,
    settings: Settings | None = None,
) -> WatchTarget | None:
    async with session_scope(settings) as session:
        return await session.get(WatchTarget, watch_target_id)


async def create_watch_target(
    payload: WatchTargetCreate,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> WatchTarget:
    async with session_scope(settings) as session:
        repository = IncidentIntelligenceRepository(session)
        return await repository.create_watch_target(payload, actor, idempotency_key)


async def patch_watch_target(
    watch_target_id: str,
    payload: WatchTargetPatch,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> WatchTarget | None:
    async with session_scope(settings) as session:
        repository = IncidentIntelligenceRepository(session)
        return await repository.patch_watch_target(watch_target_id, payload, actor, idempotency_key)


async def monitor_watch_targets(*, settings: Settings | None = None) -> dict[str, object]:
    resolved = settings or Settings()
    provider = news_provider_for_settings(resolved)
    now = datetime.now(UTC)
    async with session_scope(resolved) as session:
        repository = IncidentIntelligenceRepository(session)
        targets = await repository.list_due_monitoring_targets(now)
        checked = 0
        failed = 0
        for target in targets:
            checked += 1
            try:
                await repository.monitor_watch_target(target, provider=provider, settings=resolved)
            except Exception as exc:  # pragma: no cover - defensive per-target isolation.
                failed += 1
                await repository.record_monitoring_failure(target, provider.provider_name, str(exc))
        return {"checked": checked, "failed": failed, "provider": provider.provider_name}


async def promote_incident_to_watchlist(
    incident_id: str,
    *,
    version: int,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> WatchTarget | None:
    async with session_scope(settings) as session:
        incident = await session.get(SecurityIncident, incident_id)
        if incident is None:
            return None
        if incident.version != version:
            raise ValueError("stale optimistic version")
        if incident.status != "corroborated":
            if incident.status == "candidate":
                incident.status = "corroborated"
                incident.corroboration_method = (
                    incident.corroboration_method or "dashboard_promotion"
                )
                incident.version += 1
            else:
                raise ValueError("incident must be corroborated before watchlist promotion")
        company = incident.primary_affected_company or _string(
            (incident.affected_companies or [None])[0]
        )
        if not company:
            raise ValueError("incident does not have a company to promote")
        payload = WatchTargetCreate(
            target_type="company",
            canonical_target_key=company,
            display_name=company,
            query_config={
                "incident_id": incident.id,
                "incident_group_key": incident.incident_group_key,
                "domains": incident.affected_domains or [],
                "evidence_families": incident.evidence_families or [],
            },
            owner=actor,
            origin_incident_id=incident.id,
        )
        repository = IncidentIntelligenceRepository(session)
        return await repository.create_watch_target(payload, actor, idempotency_key)


from .parsers import _string  # noqa: E402
from .repository import IncidentIntelligenceRepository  # noqa: E402
