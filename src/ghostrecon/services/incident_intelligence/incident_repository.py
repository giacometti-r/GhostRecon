from __future__ import annotations

from sqlalchemy import select

from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.db import (
    NewsArticle,
    RawSourceItem,
    SecurityIncident,
    SecurityIncidentEvidence,
    SourceDefinition,
)


class IncidentRepositoryMixin:
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


from .candidates import (  # noqa: E402
    INCIDENT_SERVICE_NAME,
    ArticleCandidate,
    IncidentCandidate,
    article_candidate_from_raw_item,
    incident_candidates_from_article,
)
from .parsers import _append_unique, _merge_list, _slug  # noqa: E402
