from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import ManualIncidentCreate, WatchTargetCreate, WatchTargetPatch
from ghostrecon.models.db import (
    AuditEvent,
    NewsArticle,
    OutboxEvent,
    RawSourceItem,
    SecurityIncident,
    SecurityIncidentEvidence,
    SourceDefinition,
    WatchTarget,
    WatchTargetMonitoringRun,
)
from ghostrecon.services.search_adapters import (
    news_provider_for_settings,
    watch_monitoring_queries,
)
from ghostrecon.services.source_registry import fetch_source_by_id, normalize_url

INCIDENT_SERVICE_NAME = "incident-intelligence-service"
_SECURITY_TERMS = {
    "breach",
    "cyberattack",
    "cyber attack",
    "cyber incident",
    "data leak",
    "ddos",
    "malware",
    "phishing",
    "ransomware",
}
_ATTACK_VECTORS = {
    "ransomware": "ransomware",
    "phishing": "phishing",
    "ddos": "ddos",
    "malware": "malware",
    "data breach": "data_breach",
    "breach": "data_breach",
    "data leak": "data_leak",
}


@dataclass(frozen=True)
class ArticleCandidate:
    canonical_url: str
    publisher: str | None
    title: str
    permitted_excerpt: str | None
    published_at: datetime | None
    retrieved_at: datetime | None
    original_language: str | None
    translated_title: str | None = None
    translation_metadata: dict[str, object] = field(default_factory=dict)
    content_hash: str = ""
    syndication_cluster_key: str = ""
    dedupe_key: str = ""


@dataclass(frozen=True)
class IncidentCandidate:
    title: str
    incident_group_key: str
    primary_affected_company: str | None
    primary_affected_domain: str | None
    affected_companies: list[object]
    affected_domains: list[object]
    incident_type: str | None
    attack_vector: str | None
    first_observed_at: datetime | None
    last_observed_at: datetime | None
    geography: list[object]
    languages: list[object]
    confidence: int
    dedupe_key: str
    evidence_family_key: str
    evidence_urls: list[object] = field(default_factory=list)
    authoritative: bool = False


def article_candidate_from_raw_item(
    source: SourceDefinition, raw_item: RawSourceItem
) -> ArticleCandidate:
    metadata = raw_item.raw_metadata or {}
    gdelt = metadata.get("gdelt_article") if isinstance(metadata.get("gdelt_article"), dict) else {}
    title = _string(gdelt.get("title")) or _string(metadata.get("feed_title"))
    title = title or _string(metadata.get("title")) or raw_item.permitted_excerpt or source.name
    publisher = (
        _string(gdelt.get("domain"))
        or _string(gdelt.get("source"))
        or _string(metadata.get("publisher"))
        or _hostname(raw_item.canonical_url)
    )
    translated_title = _string(gdelt.get("transTitle")) or _string(metadata.get("translated_title"))
    translation_metadata = {}
    if translated_title:
        translation_metadata = {
            "provider": "gdelt" if gdelt else "source",
            "original_language": raw_item.original_language,
        }
    cluster_title = _slug(title)
    cluster_published = (
        raw_item.published_at.date().isoformat() if raw_item.published_at else "unknown"
    )
    cluster_identity = f"{cluster_title}:{cluster_published}"
    cluster_digest = hashlib.sha256(cluster_identity.encode()).hexdigest()
    syndication_cluster_key = f"article-cluster:{cluster_digest}"
    article_digest = hashlib.sha256(normalize_url(raw_item.canonical_url).encode()).hexdigest()
    dedupe_key = f"news-article:{article_digest}"
    return ArticleCandidate(
        canonical_url=normalize_url(raw_item.canonical_url),
        publisher=publisher,
        title=title[:512],
        permitted_excerpt=raw_item.permitted_excerpt,
        published_at=raw_item.published_at,
        retrieved_at=raw_item.retrieved_at,
        original_language=raw_item.original_language,
        translated_title=translated_title,
        translation_metadata=translation_metadata,
        content_hash=raw_item.content_hash,
        syndication_cluster_key=syndication_cluster_key,
        dedupe_key=dedupe_key,
    )


def incident_candidates_from_article(
    source: SourceDefinition, raw_item: RawSourceItem, article: ArticleCandidate
) -> list[IncidentCandidate]:
    metadata = raw_item.raw_metadata or {}
    gdelt = metadata.get("gdelt_article") if isinstance(metadata.get("gdelt_article"), dict) else {}
    text = " ".join(
        part
        for part in (
            article.title,
            article.permitted_excerpt,
            _string(metadata.get("feed_description")),
            _string(gdelt.get("snippet")),
        )
        if part
    )
    lowered = text.lower()
    if not any(term in lowered for term in _SECURITY_TERMS):
        return []

    companies = _companies_from_metadata(metadata) or _companies_from_text(text)
    domains = _domains_from_metadata(metadata)
    attack_vector = _attack_vector(lowered)
    incident_type = attack_vector or "security_incident"
    geography = [value for value in (_string(gdelt.get("sourcecountry")),) if value]
    languages = [article.original_language] if article.original_language else []
    family = _string(gdelt.get("domain")) or article.publisher or _hostname(article.canonical_url)
    authoritative = bool(
        source.query_scope.get("authoritative")
        or metadata.get("authoritative")
        or gdelt.get("authoritative")
    )
    key_date = article.published_at.date().isoformat() if article.published_at else "unknown"
    key_vector = attack_vector or "unknown"
    group_identity = f"{_slug(article.title)}:{key_date}:{key_vector}"
    incident_group_key = (
        f"security-incident-group:{hashlib.sha256(group_identity.encode()).hexdigest()}"
    )
    candidates = []
    for company, domain in _incident_contexts(companies, domains):
        key_company = (
            _slug(str(company))
            if company
            else _slug(str(domain or _hostname(article.canonical_url)))
        )
        incident_identity = f"{incident_group_key}:{key_company}:{domain or ''}"
        incident_digest = hashlib.sha256(incident_identity.encode()).hexdigest()
        candidates.append(
            IncidentCandidate(
                title=article.title,
                incident_group_key=incident_group_key,
                primary_affected_company=company,
                primary_affected_domain=domain,
                affected_companies=[company] if company else [],
                affected_domains=[domain] if domain else [],
                incident_type=incident_type,
                attack_vector=attack_vector,
                first_observed_at=article.published_at,
                last_observed_at=article.published_at,
                geography=geography,
                languages=languages,
                confidence=75 if company else 55,
                dedupe_key=f"security-incident:{incident_digest}",
                evidence_family_key=_slug(family or "unknown"),
                evidence_urls=[article.canonical_url],
                authoritative=authoritative,
            )
        )
    return candidates


def incident_candidate_from_article(
    source: SourceDefinition, raw_item: RawSourceItem, article: ArticleCandidate
) -> IncidentCandidate | None:
    candidates = incident_candidates_from_article(source, raw_item, article)
    return candidates[0] if candidates else None


async def fetch_incident_source(
    source_definition_id: str, settings: Settings | None = None
) -> dict[str, object]:
    fetch_result = await fetch_source_by_id(source_definition_id, settings)
    parse_result = await parse_pending_incident_items(source_definition_id, settings)
    return {"fetch": fetch_result, "parse": parse_result}


async def parse_pending_incident_items(
    source_definition_id: str | None = None, settings: Settings | None = None
) -> dict[str, object]:
    async with session_scope(settings) as session:
        repository = IncidentIntelligenceRepository(session)
        return await repository.parse_pending_items(source_definition_id)


async def list_incidents(
    *,
    status: str | None = None,
    source: str | None = None,
    company: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> list[SecurityIncident]:
    async with session_scope(settings) as session:
        repository = IncidentIntelligenceRepository(session)
        return await repository.list_incidents(
            status=status, source=source, company=company, limit=limit
        )


async def get_incident(
    incident_id: str, settings: Settings | None = None
) -> SecurityIncident | None:
    async with session_scope(settings) as session:
        return await session.get(SecurityIncident, incident_id)


async def create_manual_incident(
    payload: ManualIncidentCreate,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> list[SecurityIncident]:
    async with session_scope(settings) as session:
        group_key = f"manual-incident:{idempotency_key}"
        existing = list(
            (
                await session.execute(
                    select(SecurityIncident).where(SecurityIncident.incident_group_key == group_key)
                )
            ).scalars()
        )
        if existing:
            return existing
        incidents = []
        for index, (company, domain) in enumerate(
            _incident_contexts(payload.affected_companies, payload.affected_domains)
        ):
            dedupe_key = f"{group_key}:{index}:{_slug(company or domain or payload.title)}"
            incident = SecurityIncident(
                status="candidate",
                title=payload.title,
                incident_group_key=group_key,
                primary_affected_company=company,
                primary_affected_domain=domain,
                affected_companies=[company] if company else [],
                affected_domains=[domain] if domain else [],
                incident_type=payload.incident_type,
                attack_vector=payload.attack_vector,
                first_observed_at=payload.first_observed_at,
                last_observed_at=payload.last_observed_at or payload.first_observed_at,
                geography=list(payload.geography),
                languages=list(payload.languages),
                confidence=payload.confidence,
                evidence_article_ids=[],
                evidence_source_item_ids=list(payload.source_item_ids),
                evidence_families=["manual"],
                evidence_urls=list(payload.evidence_urls),
                corroboration_method="none",
                canonical_state="canonical",
                dedupe_key=dedupe_key,
                source_definition_id=None,
                source_item_ids=list(payload.source_item_ids),
                version=1,
            )
            session.add(incident)
            incidents.append(incident)
        await session.flush()
        for incident in incidents:
            session.add(
                AuditEvent(
                    actor=actor,
                    action="security_incident.manual_created",
                    entity_type="security_incident",
                    entity_id=incident.id,
                    idempotency_key=f"{idempotency_key}:{incident.id}",
                    payload={"source": "manual", "incident_group_key": group_key},
                )
            )
            self_event = new_event(
                event_name=EventName.SECURITY_INCIDENT_DETECTED,
                aggregate_type="security_incident",
                aggregate_id=incident.id,
                source_service=INCIDENT_SERVICE_NAME,
                source_item_ids=[str(item) for item in incident.source_item_ids],
                payload={
                    "security_incident_id": incident.id,
                    "incident_group_key": incident.incident_group_key,
                    "primary_affected_company": incident.primary_affected_company,
                    "manual": True,
                    "created_by": actor,
                },
                idempotency_key=f"security_incident.manual:{incident.id}",
            ).model_dump(mode="json")
            session.add(
                OutboxEvent(
                    event_name=self_event["event_name"],
                    aggregate_type=self_event["aggregate_type"],
                    aggregate_id=self_event["aggregate_id"],
                    idempotency_key=self_event["idempotency_key"],
                    payload=self_event,
                )
            )
        return incidents


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


class IncidentIntelligenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def parse_pending_items(
        self, source_definition_id: str | None = None
    ) -> dict[str, object]:
        stmt = (
            select(RawSourceItem, SourceDefinition)
            .join(SourceDefinition, RawSourceItem.source_definition_id == SourceDefinition.id)
            .where(SourceDefinition.source_kind == "incident")
            .where(RawSourceItem.parse_status == "pending")
            .where(RawSourceItem.duplicate_state == "canonical")
            .order_by(RawSourceItem.retrieved_at)
        )
        if source_definition_id:
            stmt = stmt.where(SourceDefinition.id == source_definition_id)
        result = await self.session.execute(stmt)

        parsed_items = 0
        failed_items = 0
        articles_created = 0
        incidents_created = 0
        incidents_corroborated = 0
        for raw_item, source in result.all():
            try:
                article_candidate = article_candidate_from_raw_item(source, raw_item)
                article, article_created = await self.upsert_article(
                    source, raw_item, article_candidate
                )
                articles_created += int(article_created)
                incident_candidates = incident_candidates_from_article(
                    source, raw_item, article_candidate
                )
                for incident_candidate in incident_candidates:
                    _, incident_created, corroborated = await self.upsert_incident(
                        source, raw_item, article, incident_candidate
                    )
                    incidents_created += int(incident_created)
                    incidents_corroborated += int(corroborated)
                raw_item.parse_status = "parsed"
                parsed_items += 1
            except Exception as exc:  # noqa: BLE001 - parse failure is persisted on the raw item.
                raw_item.parse_status = "failed"
                raw_item.quarantine_reason = str(exc)
                failed_items += 1
        return {
            "parsed_items": parsed_items,
            "failed_items": failed_items,
            "articles_ingested": articles_created,
            "incidents_detected": incidents_created,
            "incidents_corroborated": incidents_corroborated,
        }

    async def upsert_article(
        self, source: SourceDefinition, raw_item: RawSourceItem, candidate: ArticleCandidate
    ) -> tuple[NewsArticle, bool]:
        existing = await self.session.scalar(
            select(NewsArticle).where(NewsArticle.dedupe_key == candidate.dedupe_key)
        )
        if existing is not None:
            if raw_item.id not in (existing.source_item_ids or []):
                existing.source_item_ids = [*(existing.source_item_ids or []), raw_item.id]
            return existing, False

        article = NewsArticle(
            canonical_url=candidate.canonical_url,
            publisher=candidate.publisher,
            title=candidate.title,
            permitted_excerpt=candidate.permitted_excerpt,
            published_at=candidate.published_at,
            retrieved_at=candidate.retrieved_at,
            original_language=candidate.original_language,
            translated_title=candidate.translated_title,
            translation_metadata=candidate.translation_metadata,
            content_hash=candidate.content_hash,
            syndication_cluster_key=candidate.syndication_cluster_key,
            dedupe_key=candidate.dedupe_key,
            source_definition_id=source.id,
            source_item_ids=[raw_item.id],
        )
        self.session.add(article)
        await self.session.flush()
        self._enqueue_event(
            new_event(
                event_name=EventName.NEWS_ARTICLE_INGESTED,
                aggregate_type="news_article",
                aggregate_id=article.id,
                source_service=INCIDENT_SERVICE_NAME,
                source_definition_id=source.id,
                source_item_ids=[raw_item.id],
                payload={
                    "news_article_id": article.id,
                    "canonical_url": article.canonical_url,
                    "language": article.original_language,
                    "published_at": article.published_at.isoformat()
                    if article.published_at
                    else None,
                    "syndication_cluster_key": article.syndication_cluster_key,
                },
                idempotency_key=f"news_article.ingested:{article.id}",
            )
        )
        return article, True

    async def upsert_incident(
        self,
        source: SourceDefinition,
        raw_item: RawSourceItem,
        article: NewsArticle,
        candidate: IncidentCandidate,
    ) -> tuple[SecurityIncident, bool, bool]:
        existing = await self.session.scalar(
            select(SecurityIncident).where(SecurityIncident.dedupe_key == candidate.dedupe_key)
        )
        created = False
        if existing is None:
            incident = SecurityIncident(
                status="candidate",
                title=candidate.title,
                incident_group_key=candidate.incident_group_key,
                primary_affected_company=candidate.primary_affected_company,
                primary_affected_domain=candidate.primary_affected_domain,
                affected_companies=candidate.affected_companies,
                affected_domains=candidate.affected_domains,
                incident_type=candidate.incident_type,
                attack_vector=candidate.attack_vector,
                first_observed_at=candidate.first_observed_at,
                last_observed_at=candidate.last_observed_at,
                geography=candidate.geography,
                languages=candidate.languages,
                confidence=candidate.confidence,
                evidence_article_ids=[article.id],
                evidence_source_item_ids=[raw_item.id],
                evidence_families=[candidate.evidence_family_key],
                evidence_urls=candidate.evidence_urls,
                corroboration_method="none",
                canonical_state="canonical",
                dedupe_key=candidate.dedupe_key,
                source_definition_id=source.id,
                source_item_ids=[raw_item.id],
            )
            self.session.add(incident)
            await self.session.flush()
            created = True
            self._enqueue_event(
                new_event(
                    event_name=EventName.SECURITY_INCIDENT_DETECTED,
                    aggregate_type="security_incident",
                    aggregate_id=incident.id,
                    source_service=INCIDENT_SERVICE_NAME,
                    source_definition_id=source.id,
                    source_item_ids=[raw_item.id],
                    payload={
                        "security_incident_id": incident.id,
                        "status": incident.status,
                        "affected_companies": incident.affected_companies,
                        "attack_vector": incident.attack_vector,
                        "confidence": incident.confidence,
                        "evidence_article_ids": incident.evidence_article_ids,
                    },
                    idempotency_key=f"security_incident.detected:{incident.id}",
                )
            )
        else:
            incident = existing
            incident.evidence_article_ids = _append_unique(
                incident.evidence_article_ids, article.id
            )
            incident.evidence_source_item_ids = _append_unique(
                incident.evidence_source_item_ids, raw_item.id
            )
            incident.source_item_ids = _append_unique(incident.source_item_ids, raw_item.id)
            incident.evidence_families = _append_unique(
                incident.evidence_families, candidate.evidence_family_key
            )
            for url in candidate.evidence_urls:
                incident.evidence_urls = _append_unique(incident.evidence_urls, url)
            incident.languages = _merge_list(incident.languages, candidate.languages)
            incident.geography = _merge_list(incident.geography, candidate.geography)
            if candidate.last_observed_at and (
                incident.last_observed_at is None
                or candidate.last_observed_at > incident.last_observed_at
            ):
                incident.last_observed_at = candidate.last_observed_at

        await self._link_evidence(incident, article, raw_item, candidate)
        before_status = incident.status
        self._apply_corroboration(incident, candidate)
        corroborated = before_status != "corroborated" and incident.status == "corroborated"
        if corroborated:
            self._enqueue_event(
                new_event(
                    event_name=EventName.SECURITY_INCIDENT_CORROBORATED,
                    aggregate_type="security_incident",
                    aggregate_id=incident.id,
                    source_service=INCIDENT_SERVICE_NAME,
                    source_definition_id=source.id,
                    source_item_ids=incident.evidence_source_item_ids,
                    payload={
                        "security_incident_id": incident.id,
                        "method": incident.corroboration_method,
                        "evidence_article_ids": incident.evidence_article_ids,
                        "evidence_families": incident.evidence_families,
                    },
                    idempotency_key=f"security_incident.corroborated:{incident.id}:{incident.corroboration_method}",
                )
            )
        return incident, created, corroborated

    async def list_incidents(
        self, *, status: str | None, source: str | None, company: str | None, limit: int
    ) -> list[SecurityIncident]:
        stmt = select(SecurityIncident).order_by(SecurityIncident.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(SecurityIncident.status == status)
        if source:
            stmt = stmt.where(SecurityIncident.source_definition_id == source)
        result = await self.session.execute(stmt)
        incidents = list(result.scalars())
        if company:
            company_slug = _slug(company)
            incidents = [
                incident
                for incident in incidents
                if any(
                    _slug(str(item)) == company_slug for item in incident.affected_companies or []
                )
            ]
        return incidents

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
            owner=payload.owner,
            origin_incident_id=payload.origin_incident_id,
            created_by=actor,
            monitoring_status="not_run",
            next_monitoring_at=datetime.now(UTC) if payload.target_type == "company" else None,
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
                target.next_monitoring_at = datetime.now(UTC)
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

    async def _link_evidence(
        self,
        incident: SecurityIncident,
        article: NewsArticle,
        raw_item: RawSourceItem,
        candidate: IncidentCandidate,
    ) -> None:
        existing = await self.session.scalar(
            select(SecurityIncidentEvidence).where(
                SecurityIncidentEvidence.security_incident_id == incident.id,
                SecurityIncidentEvidence.news_article_id == article.id,
            )
        )
        if existing is not None:
            return
        self.session.add(
            SecurityIncidentEvidence(
                security_incident_id=incident.id,
                news_article_id=article.id,
                source_item_id=raw_item.id,
                evidence_family_key=candidate.evidence_family_key,
                authoritative=candidate.authoritative,
            )
        )

    def _apply_corroboration(
        self, incident: SecurityIncident, candidate: IncidentCandidate
    ) -> None:
        if incident.status == "rejected":
            return
        if candidate.authoritative:
            incident.status = "corroborated"
            incident.corroboration_method = "authoritative_disclosure"
        elif len(set(incident.evidence_families or [])) >= 2:
            incident.status = "corroborated"
            incident.corroboration_method = "independent_sources"

    def _audit(
        self, actor: str, action: str, entity_type: str, entity_id: str, idempotency_key: str
    ) -> None:
        self.session.add(
            AuditEvent(
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                idempotency_key=idempotency_key,
                payload={},
            )
        )

    def _enqueue_event(self, event: Any) -> OutboxEvent:
        payload = event.model_dump(mode="json")
        outbox_event = OutboxEvent(
            event_name=payload["event_name"],
            aggregate_type=payload["aggregate_type"],
            aggregate_id=payload["aggregate_id"],
            idempotency_key=payload["idempotency_key"],
            payload=payload,
        )
        self.session.add(outbox_event)
        return outbox_event


def incident_to_api(incident: SecurityIncident) -> dict[str, object]:
    return {
        "id": incident.id,
        "status": incident.status,
        "title": incident.title,
        "incident_group_key": incident.incident_group_key,
        "primary_affected_company": incident.primary_affected_company,
        "primary_affected_domain": incident.primary_affected_domain,
        "affected_companies": incident.affected_companies or [],
        "affected_domains": incident.affected_domains or [],
        "incident_type": incident.incident_type,
        "attack_vector": incident.attack_vector,
        "first_observed_at": incident.first_observed_at,
        "last_observed_at": incident.last_observed_at,
        "geography": incident.geography or [],
        "languages": incident.languages or [],
        "confidence": incident.confidence,
        "evidence_article_ids": incident.evidence_article_ids or [],
        "evidence_source_item_ids": incident.evidence_source_item_ids or [],
        "evidence_families": incident.evidence_families or [],
        "evidence_urls": incident.evidence_urls or [],
        "corroboration_method": incident.corroboration_method,
        "analyst_decision_ref": incident.analyst_decision_ref,
        "canonical_state": incident.canonical_state,
        "source_definition_id": incident.source_definition_id,
        "source_item_ids": incident.source_item_ids or [],
        "version": getattr(incident, "version", 1),
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
    }


def watch_target_to_api(target: WatchTarget) -> dict[str, object]:
    return {
        "id": target.id,
        "target_type": target.target_type,
        "canonical_target_key": target.canonical_target_key,
        "display_name": target.display_name,
        "query_config": target.query_config or {},
        "enabled": target.enabled,
        "monitoring_enabled": target.enabled,
        "monitoring_status": target.monitoring_status,
        "last_monitored_at": target.last_monitored_at,
        "next_monitoring_at": target.next_monitoring_at,
        "monitoring_error": target.monitoring_error,
        "monitoring_summary": target.monitoring_summary or {},
        "owner": target.owner,
        "origin_incident_id": target.origin_incident_id,
        "created_by": target.created_by,
        "version": target.version,
        "created_at": target.created_at,
        "updated_at": target.updated_at,
    }


def _append_unique(values: list[object] | None, value: object) -> list[object]:
    resolved = list(values or [])
    if value not in resolved:
        resolved.append(value)
    return resolved


def _merge_list(left: list[object] | None, right: list[object] | None) -> list[object]:
    merged = list(left or [])
    for item in right or []:
        if item not in merged:
            merged.append(item)
    return merged


def _companies_from_metadata(metadata: dict[str, object]) -> list[object]:
    values = metadata.get("affected_companies")
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    return []


def _companies_from_text(text: str) -> list[object]:
    disclosure_verbs = "reports|reported|discloses|disclosed|confirms|confirmed|suffers|suffered"
    incident_terms = "breach|ransomware|cyberattack|cyber attack"
    patterns = [
        rf"([A-Z][A-Za-z0-9&., ]{{2,80}}?) (?:{disclosure_verbs})",
        rf"(?:{incident_terms}) (?:at|hits|against) ([A-Z][A-Za-z0-9&., ]{{2,80}})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            company = match.group(1).strip(" .,:")
            if company:
                return [company]
    return []


def _domains_from_metadata(metadata: dict[str, object]) -> list[object]:
    values = metadata.get("affected_domains")
    if isinstance(values, list):
        return [str(value).strip().lower() for value in values if str(value).strip()]
    return []


def _incident_contexts(
    companies: list[object] | None, domains: list[object] | None
) -> list[tuple[str | None, str | None]]:
    company_values = [str(value).strip() for value in companies or [] if str(value).strip()]
    domain_values = [str(value).strip().lower() for value in domains or [] if str(value).strip()]
    if company_values:
        contexts = []
        for index, company in enumerate(company_values):
            domain = domain_values[index] if index < len(domain_values) else None
            if domain is None and len(domain_values) == 1:
                domain = domain_values[0]
            contexts.append((company, domain))
        return contexts
    if domain_values:
        return [(None, domain) for domain in domain_values]
    return [(None, None)]


def _attack_vector(lowered: str) -> str | None:
    for term, value in _ATTACK_VECTORS.items():
        if term in lowered:
            return value
    return None


def _watch_target_key(target_type: str, key: str) -> str:
    text = key.strip().lower()
    if target_type == "domain":
        return _hostname(f"https://{text}") or text
    return _slug(text)


def _hostname(url: str | None) -> str | None:
    if not url:
        return None
    return (urlsplit(url).hostname or "").lower() or None


def _string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown"
