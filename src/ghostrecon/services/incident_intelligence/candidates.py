from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from ghostrecon.models.db import (
    RawSourceItem,
    SourceDefinition,
)
from ghostrecon.services.source_registry import normalize_url

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


from .parsers import (  # noqa: E402
    _attack_vector,
    _companies_from_metadata,
    _companies_from_text,
    _domains_from_metadata,
    _hostname,
    _incident_contexts,
    _slug,
    _string,
)
