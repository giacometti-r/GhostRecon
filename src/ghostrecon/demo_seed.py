from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.db import (
    CrmTarget,
    CyberEvent,
    ReviewCandidate,
    SecurityIncident,
    SourceDefinition,
    WatchTarget,
)

DEMO_NAMESPACE = "https://ghostrecon.local/demo/sprint-14"


@dataclass(frozen=True)
class DemoSeedIds:
    source_definition_id: str = str(uuid5(NAMESPACE_URL, f"{DEMO_NAMESPACE}/source/demo-source"))
    cyber_event_id: str = str(uuid5(NAMESPACE_URL, f"{DEMO_NAMESPACE}/event/cloud-security-summit"))
    security_incident_id: str = str(
        uuid5(NAMESPACE_URL, f"{DEMO_NAMESPACE}/incident/example-ransomware")
    )
    watch_target_id: str = str(uuid5(NAMESPACE_URL, f"{DEMO_NAMESPACE}/watch/example-industries"))
    review_candidate_id: str = str(uuid5(NAMESPACE_URL, f"{DEMO_NAMESPACE}/review/example"))
    crm_target_id: str = str(uuid5(NAMESPACE_URL, f"{DEMO_NAMESPACE}/crm-target/example"))


DEMO_SEED_IDS = DemoSeedIds()
DEMO_SEED_REPORTING_RESOURCES = (
    "source_definitions",
    "cyber_events",
    "security_incidents",
    "watch_targets",
    "review_candidates",
    "crm_targets",
)


class DemoSeedSafetyError(RuntimeError):
    """Raised when demo seed is requested in a non-local environment."""


def assert_demo_seed_allowed(settings: Settings) -> None:
    if settings.environment in {"local", "dev"}:
        return
    if os.environ.get("GHOSTRECON_ALLOW_DEMO_SEED") == "1":
        return
    raise DemoSeedSafetyError(
        "refusing to seed demo data outside local/dev; set "
        "GHOSTRECON_ALLOW_DEMO_SEED=1 to override"
    )


async def seed_demo_data(settings: Settings | None = None) -> DemoSeedIds:
    resolved = settings or get_settings()
    assert_demo_seed_allowed(resolved)
    async with session_scope(resolved) as session:
        await _upsert_demo_records(session)
    return DEMO_SEED_IDS


async def _upsert_demo_records(session: AsyncSession) -> None:
    now = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    event_start = now + timedelta(days=30)
    incident_observed = now - timedelta(days=5)

    source = await _get_or_create(session, SourceDefinition, DEMO_SEED_IDS.source_definition_id)
    source.name = "GhostRecon Local Demo Source"
    source.source_kind = "demo"
    source.adapter_type = "fixture"
    source.base_url = "https://ghostrecon.local/demo"
    source.owner = "demo"
    source.query_scope = {"fixture": "sprint-14"}
    source.credentials_ref = None
    source.rate_limit_policy = {"requests_per_minute": 60}
    source.polling_interval_seconds = 86400
    source.freshness_slo_seconds = 86400
    source.checkpoint_strategy = "manual"
    source.checkpoint_state = {"seeded": True}
    source.retry_budget = 1
    source.policy_state = "allowed"
    source.policy_evidence = {"basis": "local deterministic demo fixture"}
    source.policy_reviewed_at = now
    source.participant_reuse_state = "allowed"
    source.participant_reuse_evidence = {"basis": "synthetic local fixture"}
    source.content_storage_policy = "metadata_excerpt"
    source.default_language = "en"
    source.expected_timezone = "UTC"
    source.enabled = True
    source.operating_state = "enabled"
    source.last_fetch_at = now
    source.last_success_at = now
    source.last_error_at = None
    source.last_error = None
    source.consecutive_failures = 0
    source.created_at = now
    source.updated_at = now
    await session.flush()

    event = await _get_or_create(session, CyberEvent, DEMO_SEED_IDS.cyber_event_id)
    event.name = "Cloud Security Summit Demo"
    event.event_series_key = "cloud-security-summit-demo"
    event.external_id = "demo-event-001"
    event.canonical_url = "https://ghostrecon.local/demo/events/cloud-security-summit"
    event.original_start = event_start.isoformat()
    event.original_end = (event_start + timedelta(days=2)).isoformat()
    event.source_timezone = "UTC"
    event.iana_timezone = "UTC"
    event.timezone_status = "resolved"
    event.starts_at_utc = event_start
    event.ends_at_utc = event_start + timedelta(days=2)
    event.event_format = "physical"
    event.venue_name = "Demo Convention Center"
    event.city = "Zurich"
    event.region = "ZH"
    event.country = "CH"
    event.virtual_url = None
    event.topics = ["cloud security", "incident response"]
    event.organizers = [{"name": "GhostRecon Demo Team"}]
    event.confidence = 92
    event.canonical_state = "canonical"
    event.dedupe_key = "demo:event:cloud-security-summit"
    event.source_definition_id = source.id
    event.source_item_ids = []
    event.created_at = now
    event.updated_at = now

    incident = await _get_or_create(session, SecurityIncident, DEMO_SEED_IDS.security_incident_id)
    incident.status = "corroborated"
    incident.title = "Example Industries ransomware exposure"
    incident.affected_companies = ["Example Industries"]
    incident.affected_domains = ["example-industries.test"]
    incident.incident_type = "ransomware"
    incident.attack_vector = "identity_compromise"
    incident.first_observed_at = incident_observed
    incident.last_observed_at = incident_observed + timedelta(days=1)
    incident.geography = ["US"]
    incident.languages = ["en"]
    incident.confidence = 88
    incident.evidence_article_ids = []
    incident.evidence_source_item_ids = []
    incident.evidence_families = ["demo-authoritative-disclosure"]
    incident.corroboration_method = "analyst_decision"
    incident.analyst_decision_ref = "demo-seed"
    incident.canonical_state = "canonical"
    incident.dedupe_key = "demo:incident:example-industries-ransomware"
    incident.source_definition_id = source.id
    incident.source_item_ids = []
    incident.version = 1
    incident.created_at = now
    incident.updated_at = now
    await session.flush()

    watch = await _get_or_create(session, WatchTarget, DEMO_SEED_IDS.watch_target_id)
    watch.target_type = "company"
    watch.canonical_target_key = "example-industries"
    watch.display_name = "Example Industries"
    watch.query_config = {"domains": ["example-industries.test"]}
    watch.enabled = True
    watch.owner = "demo-analyst"
    watch.origin_incident_id = incident.id
    watch.created_by = "demo-seed"
    watch.version = 1
    watch.created_at = now
    watch.updated_at = now

    review = await _get_or_create(session, ReviewCandidate, DEMO_SEED_IDS.review_candidate_id)
    review.candidate_type = "incident_corroboration"
    review.target_type = "security_incident"
    review.target_id = incident.id
    review.origin_type = "security_incident"
    review.origin_id = incident.id
    review.source_definition_id = source.id
    review.source_item_ids = []
    review.status = "open"
    review.reason_code = "demo_review"
    review.reason = "Synthetic local demo candidate for Sprint 14 health checks."
    review.evidence_summary = {
        "incident_title": incident.title,
        "affected_company": "Example Industries",
    }
    review.policy_snapshot = {"lawful_basis": "synthetic_demo"}
    review.policy_snapshot_hash = "demo-policy-snapshot"
    review.sla_due_at = now + timedelta(days=2)
    review.idempotency_key = "demo:sprint14:review:example-industries"
    review.version = 1
    review.created_at = now
    review.updated_at = now
    await session.flush()

    crm_target = await _get_or_create(session, CrmTarget, DEMO_SEED_IDS.crm_target_id)
    crm_target.review_candidate_id = review.id
    crm_target.review_decision_id = None
    crm_target.target_type = "security_incident"
    crm_target.target_id = incident.id
    crm_target.origin_type = "security_incident"
    crm_target.origin_id = incident.id
    crm_target.source_definition_id = source.id
    crm_target.source_item_ids = []
    crm_target.status = "pending_export"
    crm_target.export_status = "not_exported"
    crm_target.policy_snapshot = {"lawful_basis": "synthetic_demo"}
    crm_target.approval_snapshot = {"approved_by": "demo-seed"}
    crm_target.idempotency_key = "demo:sprint14:crm-target:example-industries"
    crm_target.version = 1
    crm_target.created_at = now
    crm_target.updated_at = now


async def _get_or_create(
    session: AsyncSession,
    model: type[SourceDefinition]
    | type[CyberEvent]
    | type[SecurityIncident]
    | type[WatchTarget]
    | type[ReviewCandidate]
    | type[CrmTarget],
    record_id: str,
):
    record = await session.get(model, record_id)
    if record is not None:
        return record
    record = model(id=record_id)
    session.add(record)
    return record


async def _seeded_counts(settings: Settings) -> dict[str, int]:
    async with session_scope(settings) as session:
        counts = {
            "source_definitions": await _count_seeded(session, SourceDefinition),
            "cyber_events": await _count_seeded(session, CyberEvent),
            "security_incidents": await _count_seeded(session, SecurityIncident),
            "watch_targets": await _count_seeded(session, WatchTarget),
            "review_candidates": await _count_seeded(session, ReviewCandidate),
            "crm_targets": await _count_seeded(session, CrmTarget),
        }
    return counts


async def _count_seeded(
    session: AsyncSession,
    model: type[SourceDefinition]
    | type[CyberEvent]
    | type[SecurityIncident]
    | type[WatchTarget]
    | type[ReviewCandidate]
    | type[CrmTarget],
) -> int:
    result = await session.execute(
        select(model).where(model.id.in_(DEMO_SEED_IDS.__dict__.values()))
    )
    return len(list(result.scalars()))


async def async_main() -> None:
    settings = get_settings()
    ids = await seed_demo_data(settings)
    counts = await _seeded_counts(settings)
    print("Seeded deterministic local demo data:")
    for table_name in DEMO_SEED_REPORTING_RESOURCES:
        print(f"  {table_name}: {counts[table_name]}")
    print(f"  source_definition_id: {ids.source_definition_id}")
    print(f"  cyber_event_id: {ids.cyber_event_id}")
    print(f"  security_incident_id: {ids.security_incident_id}")


def main() -> None:
    try:
        asyncio.run(async_main())
    except DemoSeedSafetyError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
