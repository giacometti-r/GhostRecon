from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.models.db import (
    SecurityIncident,
    SourceDefinition,
    WatchTarget,
    WatchTargetMonitoringRun,
)

from .ids import DEMO_SEED_IDS
from .persistence import _get_or_create


async def _source(
    session: AsyncSession,
    record_id: str,
    *,
    now: datetime,
    name: str,
    source_kind: str,
    adapter_type: str,
    operating_state: str,
    last_success_at: datetime,
    consecutive_failures: int,
    last_error: str | None,
    checkpoint_state: dict[str, object],
) -> SourceDefinition:
    source = await _get_or_create(session, SourceDefinition, record_id)
    source.name = name
    source.source_kind = source_kind
    source.adapter_type = adapter_type
    source.base_url = "https://ghostrecon.local/demo"
    source.owner = "demo"
    source.query_scope = {"fixture": "sprint-15", "kind": source_kind}
    source.credentials_ref = None
    source.rate_limit_policy = {"requests_per_minute": 60}
    source.polling_interval_seconds = 86400
    source.freshness_slo_seconds = 86400
    source.checkpoint_strategy = "manual"
    source.checkpoint_state = checkpoint_state
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
    source.operating_state = operating_state
    source.last_fetch_at = now
    source.last_success_at = last_success_at
    source.last_error_at = now if last_error else None
    source.last_error = last_error
    source.consecutive_failures = consecutive_failures
    source.created_at = now
    source.updated_at = now
    return source


def _apply_incident(
    incident: SecurityIncident,
    *,
    now: datetime,
    observed_at: datetime,
    title: str,
    affected_companies: list[str],
    affected_domains: list[str],
    incident_type: str,
    attack_vector: str,
    status: str,
    confidence: int,
    dedupe_key: str,
    source_definition_id: str,
    incident_group_key: str | None = None,
    corroboration_method: str = "none",
    evidence_urls: list[str] | None = None,
) -> None:
    incident.status = status
    incident.title = title
    incident.incident_group_key = incident_group_key or dedupe_key
    incident.primary_affected_company = affected_companies[0] if affected_companies else None
    incident.primary_affected_domain = affected_domains[0] if affected_domains else None
    incident.affected_companies = affected_companies
    incident.affected_domains = affected_domains
    incident.incident_type = incident_type
    incident.attack_vector = attack_vector
    incident.first_observed_at = observed_at
    incident.last_observed_at = observed_at + timedelta(days=1)
    incident.geography = ["US"]
    incident.languages = ["en"]
    incident.confidence = confidence
    incident.evidence_article_ids = []
    incident.evidence_source_item_ids = []
    incident.evidence_families = ["demo-authoritative-disclosure"]
    incident.evidence_urls = list(evidence_urls or [])
    incident.corroboration_method = corroboration_method
    incident.analyst_decision_ref = None
    incident.canonical_state = "canonical"
    incident.dedupe_key = dedupe_key
    incident.source_definition_id = source_definition_id
    incident.source_item_ids = []
    incident.version = 1
    incident.created_at = now
    incident.updated_at = now


async def _watch_monitoring_run(
    session: AsyncSession, *, now: datetime, watch: WatchTarget
) -> WatchTargetMonitoringRun:
    run = await _get_or_create(
        session,
        WatchTargetMonitoringRun,
        DEMO_SEED_IDS.watch_monitoring_run_id,
    )
    run.watch_target_id = watch.id
    run.provider = "local_demo"
    run.status = "completed"
    run.query_summary = {
        "queries": [
            '"Example Industries" ("new CISO" OR "appointed CISO" OR '
            '"Chief Information Security Officer")',
            '"Example Industries" (cyberattack OR "cyber attack" OR ransomware OR "data breach")',
        ]
    }
    run.result_summary = watch.monitoring_summary
    run.error = None
    run.started_at = now - timedelta(hours=1, minutes=1)
    run.completed_at = now - timedelta(hours=1)
    run.created_at = now - timedelta(hours=1, minutes=1)
    return run


async def _seed_incidents(
    session: AsyncSession,
    now: datetime,
    incident_observed: datetime,
    degraded_source: SourceDefinition,
):
    incident = await _get_or_create(session, SecurityIncident, DEMO_SEED_IDS.security_incident_id)
    ransomware_group_key = "demo:sprint17:incident-group:example-contoso-ransomware"
    _apply_incident(
        incident,
        now=now,
        observed_at=incident_observed,
        title="Example Industries and Contoso ransomware exposure",
        affected_companies=["Example Industries"],
        affected_domains=["example-industries.test"],
        incident_type="ransomware",
        attack_vector="identity_compromise",
        status="corroborated",
        confidence=88,
        dedupe_key="demo:sprint15:incident:example-industries-ransomware",
        source_definition_id=degraded_source.id,
        incident_group_key=ransomware_group_key,
        corroboration_method="analyst_decision",
        evidence_urls=["https://ghostrecon.local/demo/incidents/example-contoso-ransomware"],
    )
    secondary_incident = await _get_or_create(
        session, SecurityIncident, DEMO_SEED_IDS.secondary_incident_id
    )
    _apply_incident(
        secondary_incident,
        now=now,
        observed_at=incident_observed,
        title="Example Industries and Contoso ransomware exposure",
        affected_companies=["Contoso Manufacturing"],
        affected_domains=["contoso-manufacturing.test"],
        incident_type="ransomware",
        attack_vector="identity_compromise",
        status="corroborated",
        confidence=84,
        dedupe_key="demo:sprint17:incident:contoso-ransomware",
        source_definition_id=degraded_source.id,
        incident_group_key=ransomware_group_key,
        corroboration_method="analyst_decision",
        evidence_urls=["https://ghostrecon.local/demo/incidents/example-contoso-ransomware"],
    )

    review_incident = await _get_or_create(
        session, SecurityIncident, DEMO_SEED_IDS.review_incident_id
    )
    _apply_incident(
        review_incident,
        now=now,
        observed_at=incident_observed - timedelta(days=2),
        title="Nimbus Retail phishing campaign mention",
        affected_companies=["Nimbus Retail"],
        affected_domains=["nimbus-retail.test"],
        incident_type="phishing",
        attack_vector="credential_harvesting",
        status="candidate",
        confidence=61,
        dedupe_key="demo:sprint15:incident:nimbus-retail-phishing",
        source_definition_id=degraded_source.id,
        evidence_urls=["https://ghostrecon.local/demo/incidents/nimbus-retail-phishing"],
    )
    await session.flush()

    watch = await _get_or_create(session, WatchTarget, DEMO_SEED_IDS.watch_target_id)
    watch.target_type = "company"
    watch.canonical_target_key = "example-industries"
    watch.display_name = "Example Industries"
    watch.query_config = {"domains": ["example-industries.test"], "topics": ["ransomware"]}
    watch.enabled = True
    watch.monitoring_status = "completed"
    watch.last_monitored_at = now - timedelta(hours=1)
    watch.next_monitoring_at = now + timedelta(hours=1)
    watch.monitoring_error = None
    watch.monitoring_summary = {
        "provider": "local_demo",
        "result_count": 2,
        "top_results": [
            {
                "title": "Example Industries appoints new CISO",
                "url": "https://ghostrecon.local/demo/news/example-industries-ciso",
                "source": "local_demo_news",
            }
        ],
    }
    watch.owner = "demo-analyst"
    watch.origin_incident_id = incident.id
    watch.created_by = "demo-seed"
    watch.version = 1
    watch.created_at = now
    watch.updated_at = now
    return incident, review_incident, watch
