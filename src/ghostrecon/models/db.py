from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ghostrecon.common.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class SourceDefinition(Base):
    __tablename__ = "source_definitions"
    __table_args__ = (
        UniqueConstraint("name", name="uq_source_definitions_name"),
        Index("ix_source_definitions_kind_enabled", "source_kind", "enabled"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(255))
    source_kind: Mapped[str] = mapped_column(String(64), index=True)
    adapter_type: Mapped[str] = mapped_column(String(64))
    base_url: Mapped[str] = mapped_column(String(2048))
    owner: Mapped[str | None] = mapped_column(String(128))
    query_scope: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    credentials_ref: Mapped[str | None] = mapped_column(String(255))
    rate_limit_policy: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    polling_interval_seconds: Mapped[int | None] = mapped_column(Integer)
    freshness_slo_seconds: Mapped[int] = mapped_column(Integer, default=86400)
    checkpoint_strategy: Mapped[str | None] = mapped_column(String(64))
    checkpoint_state: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    retry_budget: Mapped[int] = mapped_column(Integer, default=3)
    policy_state: Mapped[str] = mapped_column(String(64), default="unknown")
    policy_evidence: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    policy_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    participant_reuse_state: Mapped[str] = mapped_column(String(64), default="unknown")
    participant_reuse_evidence: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    content_storage_policy: Mapped[str] = mapped_column(String(64), default="metadata_excerpt")
    default_language: Mapped[str | None] = mapped_column(String(16))
    expected_timezone: Mapped[str | None] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    operating_state: Mapped[str] = mapped_column(String(64), default="enabled")
    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    raw_items: Mapped[list["RawSourceItem"]] = relationship(back_populates="source_definition")


class RawSourceItem(Base):
    __tablename__ = "raw_source_items"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_raw_source_items_idempotency_key"),
        UniqueConstraint(
            "source_definition_id",
            "external_id",
            name="uq_raw_source_items_source_external_id",
        ),
        UniqueConstraint(
            "source_definition_id",
            "canonical_url",
            "content_hash",
            name="uq_raw_source_items_source_url_hash",
        ),
        Index("ix_raw_source_items_source_retrieved", "source_definition_id", "retrieved_at"),
        Index("ix_raw_source_items_parse_status", "parse_status"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    source_definition_id: Mapped[str] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="CASCADE")
    )
    external_id: Mapped[str | None] = mapped_column(String(512))
    original_url: Mapped[str | None] = mapped_column(String(2048))
    canonical_url: Mapped[str] = mapped_column(String(2048))
    content_hash: Mapped[str] = mapped_column(String(64))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    original_language: Mapped[str | None] = mapped_column(String(16))
    source_timezone: Mapped[str | None] = mapped_column(String(64))
    raw_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    permitted_excerpt: Mapped[str | None] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(String(64), default="pending")
    duplicate_state: Mapped[str] = mapped_column(String(64), default="canonical")
    quarantine_reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    source_definition: Mapped[SourceDefinition] = relationship(back_populates="raw_items")


class CyberEvent(Base):
    __tablename__ = "cyber_events"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_cyber_events_dedupe_key"),
        Index("ix_cyber_events_series_start", "event_series_key", "starts_at_utc"),
        Index("ix_cyber_events_source_definition", "source_definition_id"),
        Index("ix_cyber_events_canonical_state", "canonical_state"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(255))
    event_series_key: Mapped[str] = mapped_column(String(128))
    external_id: Mapped[str | None] = mapped_column(String(512))
    canonical_url: Mapped[str | None] = mapped_column(String(2048))
    original_start: Mapped[str | None] = mapped_column(String(128))
    original_end: Mapped[str | None] = mapped_column(String(128))
    source_timezone: Mapped[str | None] = mapped_column(String(64))
    iana_timezone: Mapped[str | None] = mapped_column(String(64))
    timezone_status: Mapped[str] = mapped_column(String(64), default="resolved")
    starts_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_format: Mapped[str] = mapped_column(String(64), default="unknown")
    venue_name: Mapped[str | None] = mapped_column(String(255))
    street_address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(128))
    region: Mapped[str | None] = mapped_column(String(128))
    postcode: Mapped[str | None] = mapped_column(String(32))
    country: Mapped[str | None] = mapped_column(String(2))
    virtual_url: Mapped[str | None] = mapped_column(String(2048))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    geocode_status: Mapped[str] = mapped_column(String(64), default="not_required")
    geocode_provider: Mapped[str | None] = mapped_column(String(64))
    geocode_display_name: Mapped[str | None] = mapped_column(String(512))
    geocoded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    topics: Mapped[list[object]] = mapped_column(JSONB, default=list)
    organizers: Mapped[list[object]] = mapped_column(JSONB, default=list)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    canonical_state: Mapped[str] = mapped_column(String(64), default="canonical")
    dedupe_key: Mapped[str] = mapped_column(String(255))
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    participants: Mapped[list["EventParticipant"]] = relationship(back_populates="event")


class EventParticipant(Base):
    __tablename__ = "event_participants"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_event_participants_dedupe_key"),
        Index("ix_event_participants_event", "cyber_event_id"),
        Index("ix_event_participants_source_item", "source_item_id"),
        Index("ix_event_participants_reuse", "reuse_state"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    cyber_event_id: Mapped[str] = mapped_column(ForeignKey("cyber_events.id", ondelete="CASCADE"))
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("raw_source_items.id", ondelete="SET NULL")
    )
    source_participant_id: Mapped[str | None] = mapped_column(String(512))
    published_name: Mapped[str] = mapped_column(String(255))
    organization: Mapped[str | None] = mapped_column(String(255))
    published_role: Mapped[str | None] = mapped_column(String(255))
    participant_type: Mapped[str] = mapped_column(String(64), default="speaker")
    profile_url: Mapped[str | None] = mapped_column(String(2048))
    reuse_state: Mapped[str] = mapped_column(String(64), default="unknown")
    reuse_evidence: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    contact_extraction_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    crm_export_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_confidence: Mapped[int] = mapped_column(Integer, default=0)
    dedupe_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    event: Mapped[CyberEvent] = relationship(back_populates="participants")


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_news_articles_dedupe_key"),
        Index("ix_news_articles_published", "published_at"),
        Index("ix_news_articles_source_definition", "source_definition_id"),
        Index("ix_news_articles_syndication", "syndication_cluster_key"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    canonical_url: Mapped[str] = mapped_column(String(2048))
    publisher: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(512))
    permitted_excerpt: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    original_language: Mapped[str | None] = mapped_column(String(16))
    translated_title: Mapped[str | None] = mapped_column(String(512))
    translation_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64))
    syndication_cluster_key: Mapped[str] = mapped_column(String(255))
    dedupe_key: Mapped[str] = mapped_column(String(255))
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    evidence_links: Mapped[list["SecurityIncidentEvidence"]] = relationship(
        back_populates="article"
    )


class SecurityIncident(Base):
    __tablename__ = "security_incidents"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_security_incidents_dedupe_key"),
        Index("ix_security_incidents_status", "status"),
        Index("ix_security_incidents_source_definition", "source_definition_id"),
        Index("ix_security_incidents_canonical_state", "canonical_state"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    status: Mapped[str] = mapped_column(String(64), default="candidate")
    title: Mapped[str] = mapped_column(String(512))
    incident_group_key: Mapped[str | None] = mapped_column(String(255))
    primary_affected_company: Mapped[str | None] = mapped_column(String(255))
    primary_affected_domain: Mapped[str | None] = mapped_column(String(255))
    affected_companies: Mapped[list[object]] = mapped_column(JSONB, default=list)
    affected_domains: Mapped[list[object]] = mapped_column(JSONB, default=list)
    incident_type: Mapped[str | None] = mapped_column(String(128))
    attack_vector: Mapped[str | None] = mapped_column(String(128))
    first_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    geography: Mapped[list[object]] = mapped_column(JSONB, default=list)
    languages: Mapped[list[object]] = mapped_column(JSONB, default=list)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    evidence_article_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    evidence_source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    evidence_families: Mapped[list[object]] = mapped_column(JSONB, default=list)
    evidence_urls: Mapped[list[object]] = mapped_column(JSONB, default=list)
    corroboration_method: Mapped[str] = mapped_column(String(64), default="none")
    analyst_decision_ref: Mapped[str | None] = mapped_column(String(255))
    canonical_state: Mapped[str] = mapped_column(String(64), default="canonical")
    dedupe_key: Mapped[str] = mapped_column(String(255))
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    evidence_links: Mapped[list["SecurityIncidentEvidence"]] = relationship(
        back_populates="incident"
    )


class SecurityIncidentEvidence(Base):
    __tablename__ = "security_incident_evidence"
    __table_args__ = (
        UniqueConstraint(
            "security_incident_id",
            "news_article_id",
            name="uq_security_incident_evidence_incident_article",
        ),
        Index("ix_security_incident_evidence_incident", "security_incident_id"),
        Index("ix_security_incident_evidence_article", "news_article_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    security_incident_id: Mapped[str] = mapped_column(
        ForeignKey("security_incidents.id", ondelete="CASCADE")
    )
    news_article_id: Mapped[str] = mapped_column(ForeignKey("news_articles.id", ondelete="CASCADE"))
    source_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("raw_source_items.id", ondelete="SET NULL")
    )
    evidence_family_key: Mapped[str] = mapped_column(String(255))
    evidence_role: Mapped[str] = mapped_column(String(64), default="coverage")
    authoritative: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    incident: Mapped[SecurityIncident] = relationship(back_populates="evidence_links")
    article: Mapped[NewsArticle] = relationship(back_populates="evidence_links")


class WatchTarget(Base):
    __tablename__ = "watch_targets"
    __table_args__ = (
        UniqueConstraint(
            "target_type",
            "canonical_target_key",
            name="uq_watch_targets_type_key",
        ),
        Index("ix_watch_targets_type_enabled", "target_type", "enabled"),
        Index("ix_watch_targets_origin_incident", "origin_incident_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    target_type: Mapped[str] = mapped_column(String(64))
    canonical_target_key: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    query_config: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    owner: Mapped[str | None] = mapped_column(String(128))
    monitoring_status: Mapped[str] = mapped_column(String(64), default="not_run")
    last_monitored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_monitoring_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    monitoring_error: Mapped[str | None] = mapped_column(Text)
    monitoring_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    origin_incident_id: Mapped[str | None] = mapped_column(
        ForeignKey("security_incidents.id", ondelete="SET NULL")
    )
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WatchTargetMonitoringRun(Base):
    __tablename__ = "watch_target_monitoring_runs"
    __table_args__ = (
        Index("ix_watch_target_monitoring_runs_target", "watch_target_id", "started_at"),
        Index("ix_watch_target_monitoring_runs_status", "status"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    watch_target_id: Mapped[str] = mapped_column(
        ForeignKey("watch_targets.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64), default="completed")
    query_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    result_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EntityResolutionCase(Base):
    __tablename__ = "entity_resolution_cases"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_entity_resolution_cases_idempotency_key"),
        Index("ix_entity_resolution_cases_origin", "origin_type", "origin_id"),
        Index("ix_entity_resolution_cases_status", "status"),
        Index("ix_entity_resolution_cases_domain", "input_domain"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    origin_type: Mapped[str] = mapped_column(String(64))
    origin_id: Mapped[str] = mapped_column(String(128))
    entity_kind: Mapped[str] = mapped_column(String(64), default="organization")
    input_name: Mapped[str | None] = mapped_column(String(255))
    input_domain: Mapped[str | None] = mapped_column(String(255))
    resolved_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    resolved_name: Mapped[str | None] = mapped_column(String(255))
    resolved_domain: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64), default="pending")
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    alternatives: Mapped[list[object]] = mapped_column(JSONB, default=list)
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    review_reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ContactEnrichmentCandidate(Base):
    __tablename__ = "contact_enrichment_candidates"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key", name="uq_contact_enrichment_candidates_idempotency_key"
        ),
        Index("ix_contact_enrichment_candidates_origin", "origin_type", "origin_id"),
        Index("ix_contact_enrichment_candidates_status", "status"),
        Index("ix_contact_enrichment_candidates_account", "account_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    entity_resolution_case_id: Mapped[str | None] = mapped_column(
        ForeignKey("entity_resolution_cases.id", ondelete="SET NULL")
    )
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    origin_type: Mapped[str] = mapped_column(String(64))
    origin_id: Mapped[str] = mapped_column(String(128))
    published_name: Mapped[str] = mapped_column(String(255))
    organization: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(255))
    role_scope: Mapped[str] = mapped_column(String(64), default="unknown")
    domain: Mapped[str | None] = mapped_column(String(255))
    profile_url: Mapped[str | None] = mapped_column(String(2048))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(64), default="pending")
    eligibility_reason: Mapped[str | None] = mapped_column(Text)
    reuse_state: Mapped[str] = mapped_column(String(64), default="unknown")
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    candidate_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    review_reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class OrganizationEmailPattern(Base):
    __tablename__ = "organization_email_patterns"
    __table_args__ = (
        UniqueConstraint("domain", "pattern", name="uq_organization_email_patterns_domain_pattern"),
        UniqueConstraint("idempotency_key", name="uq_organization_email_patterns_idempotency_key"),
        Index("ix_organization_email_patterns_domain", "domain"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    domain: Mapped[str] = mapped_column(String(255))
    pattern: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    sample_size: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(64), default="verification")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ReviewCandidate(Base):
    __tablename__ = "review_candidates"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_review_candidates_idempotency_key"),
        Index("ix_review_candidates_status", "status"),
        Index("ix_review_candidates_type", "candidate_type"),
        Index("ix_review_candidates_target", "target_type", "target_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    candidate_type: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(128))
    origin_type: Mapped[str | None] = mapped_column(String(64))
    origin_id: Mapped[str | None] = mapped_column(String(128))
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(64), default="open")
    reason_code: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    policy_snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CandidateScore(Base):
    __tablename__ = "candidate_scores"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_candidate_scores_idempotency_key"),
        Index("ix_candidate_scores_target", "target_type", "target_id"),
        Index("ix_candidate_scores_route", "route"),
        Index("ix_candidate_scores_origin", "origin_type", "origin_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(128))
    origin_type: Mapped[str | None] = mapped_column(String(64))
    origin_id: Mapped[str | None] = mapped_column(String(128))
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    config_version: Mapped[str] = mapped_column(String(64))
    component_scores: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    composite_score: Mapped[int] = mapped_column(Integer, default=0)
    route: Mapped[str] = mapped_column(String(64))
    reasons: Mapped[list[object]] = mapped_column(JSONB, default=list)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    policy_snapshot_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_review_decisions_idempotency_key"),
        Index("ix_review_decisions_candidate", "review_candidate_id"),
        Index("ix_review_decisions_target", "target_type", "target_id"),
        Index("ix_review_decisions_decision", "decision"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    review_candidate_id: Mapped[str | None] = mapped_column(
        ForeignKey("review_candidates.id", ondelete="SET NULL")
    )
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(128))
    decision: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(128))
    reason_code: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    policy_snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CrmTarget(Base):
    __tablename__ = "crm_targets"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_crm_targets_idempotency_key"),
        Index("ix_crm_targets_target", "target_type", "target_id"),
        Index("ix_crm_targets_status", "status"),
        Index("ix_crm_targets_origin", "origin_type", "origin_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    review_candidate_id: Mapped[str | None] = mapped_column(
        ForeignKey("review_candidates.id", ondelete="SET NULL")
    )
    review_decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("review_decisions.id", ondelete="SET NULL")
    )
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(128))
    origin_type: Mapped[str | None] = mapped_column(String(64))
    origin_id: Mapped[str | None] = mapped_column(String(128))
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(64), default="pending_export")
    export_status: Mapped[str] = mapped_column(String(64), default="not_exported")
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    approval_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CrmExportBatch(Base):
    __tablename__ = "crm_export_batches"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_crm_export_batches_idempotency_key"),
        Index("ix_crm_export_batches_provider_status", "provider", "status"),
        Index("ix_crm_export_batches_requested_by", "requested_by"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    provider: Mapped[str] = mapped_column(String(64), default="attio")
    workspace_id: Mapped[str | None] = mapped_column(String(128))
    requested_by: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(64), default="pending")
    crm_target_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    selection_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    counts: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    reconciliation_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    items: Mapped[list["CrmExportItem"]] = relationship(back_populates="batch")


class CrmExportItem(Base):
    __tablename__ = "crm_export_items"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "crm_target_id",
            name="uq_crm_export_items_batch_target",
        ),
        Index("ix_crm_export_items_batch_status", "batch_id", "status"),
        Index("ix_crm_export_items_target", "target_type", "target_id"),
        Index("ix_crm_export_items_provider_record", "provider_object", "provider_record_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    batch_id: Mapped[str] = mapped_column(ForeignKey("crm_export_batches.id", ondelete="CASCADE"))
    crm_target_id: Mapped[str] = mapped_column(ForeignKey("crm_targets.id", ondelete="CASCADE"))
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(128))
    operation: Mapped[str] = mapped_column(String(64), default="upsert_record")
    dependency_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    provider_object: Mapped[str] = mapped_column(String(128))
    provider_record_id: Mapped[str | None] = mapped_column(String(255))
    provider_list_id: Mapped[str | None] = mapped_column(String(255))
    provider_list_entry_id: Mapped[str | None] = mapped_column(String(255))
    stable_match_key: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64), default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer)
    reconciliation_state: Mapped[str] = mapped_column(String(64), default="not_required")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    batch: Mapped[CrmExportBatch] = relationship(back_populates="items")


class MeetingHandoff(Base):
    __tablename__ = "meeting_handoffs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_meeting_handoffs_idempotency_key"),
        Index("ix_meeting_handoffs_status_start", "status", "start_at"),
        Index("ix_meeting_handoffs_crm_target", "crm_target_id"),
        Index("ix_meeting_handoffs_contact_status", "contact_id", "status"),
        Index("ix_meeting_handoffs_provider_event", "calendar_provider", "provider_event_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    crm_target_id: Mapped[str | None] = mapped_column(
        ForeignKey("crm_targets.id", ondelete="SET NULL")
    )
    sequence_enrollment_id: Mapped[str | None] = mapped_column(
        ForeignKey("sequence_enrollments.id", ondelete="SET NULL")
    )
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(64), default="scheduled")
    subject: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(512))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    attendees: Mapped[list[object]] = mapped_column(JSONB, default=list)
    calendar_provider: Mapped[str] = mapped_column(String(64), default="google")
    calendar_id: Mapped[str | None] = mapped_column(String(512))
    provider_event_id: Mapped[str | None] = mapped_column(String(512))
    provider_html_link: Mapped[str | None] = mapped_column(String(2048))
    provider_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    outcome_status: Mapped[str | None] = mapped_column(String(64))
    outcome_notes: Mapped[str | None] = mapped_column(Text)
    next_steps: Mapped[list[object]] = mapped_column(JSONB, default=list)
    crm_sync_status: Mapped[str] = mapped_column(String(64), default="pending")
    crm_sync_error: Mapped[str | None] = mapped_column(Text)
    crm_retry_after_seconds: Mapped[int | None] = mapped_column(Integer)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    prep_packets: Mapped[list["MeetingPrepPacket"]] = relationship(back_populates="meeting")
    follow_up_tasks: Mapped[list["MeetingFollowUpTask"]] = relationship(back_populates="meeting")


class MeetingPrepPacket(Base):
    __tablename__ = "meeting_prep_packets"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_meeting_prep_packets_idempotency_key"),
        Index("ix_meeting_prep_packets_meeting", "meeting_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meeting_handoffs.id", ondelete="CASCADE"))
    account_summary: Mapped[str] = mapped_column(Text)
    stakeholder_map: Mapped[list[object]] = mapped_column(JSONB, default=list)
    likely_security_priorities: Mapped[list[object]] = mapped_column(JSONB, default=list)
    suggested_questions: Mapped[list[object]] = mapped_column(JSONB, default=list)
    risks: Mapped[list[object]] = mapped_column(JSONB, default=list)
    source_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    generated_by: Mapped[str] = mapped_column(String(128), default="system")
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    meeting: Mapped[MeetingHandoff] = relationship(back_populates="prep_packets")


class MeetingFollowUpTask(Base):
    __tablename__ = "meeting_follow_up_tasks"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_meeting_follow_up_tasks_idempotency_key"),
        Index("ix_meeting_follow_up_tasks_meeting", "meeting_id"),
        Index("ix_meeting_follow_up_tasks_status_due", "status", "due_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meeting_handoffs.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(128))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(64), default="open")
    crm_sync_status: Mapped[str] = mapped_column(String(64), default="pending")
    provider_task_id: Mapped[str | None] = mapped_column(String(512))
    last_error: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    meeting: Mapped[MeetingHandoff] = relationship(back_populates="follow_up_tasks")


class Sequence(Base):
    __tablename__ = "sequences"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_sequences_idempotency_key"),
        Index("ix_sequences_status_owner", "status", "owner_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[str | None] = mapped_column(String(128))
    channel: Mapped[str] = mapped_column(String(64), default="email")
    status: Mapped[str] = mapped_column(String(64), default="active")
    rate_limit_policy: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    definition_version: Mapped[int] = mapped_column(Integer, default=1)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    steps: Mapped[list["SequenceStep"]] = relationship(back_populates="sequence")
    enrollments: Mapped[list["SequenceEnrollment"]] = relationship(back_populates="sequence")


class SequenceStep(Base):
    __tablename__ = "sequence_steps"
    __table_args__ = (
        UniqueConstraint(
            "sequence_id",
            "definition_version",
            "step_order",
            name="uq_sequence_steps_version_order",
        ),
        Index("ix_sequence_steps_sequence_order", "sequence_id", "step_order"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    sequence_id: Mapped[str] = mapped_column(ForeignKey("sequences.id", ondelete="CASCADE"))
    step_order: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(64), default="email")
    delay_seconds: Mapped[int] = mapped_column(Integer, default=0)
    subject_template: Mapped[str | None] = mapped_column(String(512))
    body_template: Mapped[str | None] = mapped_column(Text)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    step_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    definition_version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    sequence: Mapped[Sequence] = relationship(back_populates="steps")


class SequenceEnrollment(Base):
    __tablename__ = "sequence_enrollments"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_sequence_enrollments_idempotency_key"),
        Index("ix_sequence_enrollments_status_next", "status", "next_step_at"),
        Index("ix_sequence_enrollments_contact_status", "contact_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    sequence_id: Mapped[str] = mapped_column(ForeignKey("sequences.id", ondelete="CASCADE"))
    crm_target_id: Mapped[str] = mapped_column(ForeignKey("crm_targets.id", ondelete="CASCADE"))
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(64), default="active")
    approval_actor: Mapped[str] = mapped_column(String(128))
    approval_reason: Mapped[str] = mapped_column(Text)
    current_step_order: Mapped[int] = mapped_column(Integer, default=1)
    definition_version: Mapped[int] = mapped_column(Integer, default=1)
    next_step_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pause_reason: Mapped[str | None] = mapped_column(Text)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sequence: Mapped[Sequence] = relationship(back_populates="enrollments")


class SequenceStepActivity(Base):
    __tablename__ = "sequence_step_activities"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_sequence_step_activities_idempotency_key"),
        Index("ix_sequence_step_activities_status_due", "status", "due_at"),
        Index("ix_sequence_step_activities_enrollment", "enrollment_id"),
        Index("ix_sequence_step_activities_step", "sequence_step_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    enrollment_id: Mapped[str] = mapped_column(
        ForeignKey("sequence_enrollments.id", ondelete="CASCADE")
    )
    sequence_step_id: Mapped[str] = mapped_column(ForeignKey("sequence_steps.id"))
    outbound_email_id: Mapped[str | None] = mapped_column(
        ForeignKey("outbound_emails.id", ondelete="SET NULL")
    )
    meeting_handoff_id: Mapped[str | None] = mapped_column(
        ForeignKey("meeting_handoffs.id", ondelete="SET NULL")
    )
    step_order: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(64), default="email")
    status: Mapped[str] = mapped_column(String(64), default="pending")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[str | None] = mapped_column(String(128))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_payload: Mapped[dict[str, object]] = mapped_column("metadata", JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class OutboundEmail(Base):
    __tablename__ = "outbound_emails"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_outbound_emails_idempotency_key"),
        Index("ix_outbound_emails_enrollment_status", "enrollment_id", "status"),
        Index("ix_outbound_emails_sent", "channel", "sent_at"),
        Index("ix_outbound_emails_to_email", "to_email"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    enrollment_id: Mapped[str] = mapped_column(
        ForeignKey("sequence_enrollments.id", ondelete="CASCADE")
    )
    sequence_step_id: Mapped[str] = mapped_column(ForeignKey("sequence_steps.id"))
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(64), default="email")
    to_email: Mapped[str] = mapped_column(String(320))
    from_email: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(512))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), default="pending")
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class InboundEmailEvent(Base):
    __tablename__ = "inbound_email_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_inbound_email_events_idempotency_key"),
        Index("ix_inbound_email_events_type_occurred", "event_type", "occurred_at"),
        Index("ix_inbound_email_events_from_email", "from_email"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    enrollment_id: Mapped[str | None] = mapped_column(
        ForeignKey("sequence_enrollments.id", ondelete="SET NULL")
    )
    outbound_email_id: Mapped[str | None] = mapped_column(
        ForeignKey("outbound_emails.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(64))
    from_email: Mapped[str | None] = mapped_column(String(320))
    to_email: Mapped[str | None] = mapped_column(String(320))
    message_id: Mapped[str | None] = mapped_column(String(255))
    provider_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SequenceSuppressionEvent(Base):
    __tablename__ = "sequence_suppression_events"
    __table_args__ = (
        Index("ix_sequence_suppression_events_email", "email"),
        Index("ix_sequence_suppression_events_enrollment", "enrollment_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    enrollment_id: Mapped[str | None] = mapped_column(
        ForeignKey("sequence_enrollments.id", ondelete="SET NULL")
    )
    suppression_id: Mapped[str | None] = mapped_column(
        ForeignKey("suppressions.id", ondelete="SET NULL")
    )
    email: Mapped[str | None] = mapped_column(String(320))
    domain: Mapped[str | None] = mapped_column(String(255))
    channel: Mapped[str] = mapped_column(String(64), default="email")
    reason: Mapped[str] = mapped_column(String(255))
    source_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("inbound_email_events.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SequenceEmailAlert(Base):
    __tablename__ = "sequence_email_alerts"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_sequence_email_alerts_idempotency_key"),
        Index("ix_sequence_email_alerts_enrollment_status", "enrollment_id", "status"),
        Index("ix_sequence_email_alerts_due", "status", "send_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    enrollment_id: Mapped[str] = mapped_column(
        ForeignKey("sequence_enrollments.id", ondelete="CASCADE")
    )
    recipient_email: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(512))
    body: Mapped[str] = mapped_column(Text)
    send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(64), default="pending")
    actor: Mapped[str] = mapped_column(String(128), default="system")
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    crm_account_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    hq_country: Mapped[str | None] = mapped_column(String(2))
    employee_count: Mapped[int | None] = mapped_column(Integer)
    revenue_band: Mapped[str | None] = mapped_column(String(64))
    industry: Mapped[str | None] = mapped_column(String(128))
    sub_industry: Mapped[str | None] = mapped_column(String(128))
    tech_stack: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    security_stack: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    intent_topics: Mapped[list[object]] = mapped_column(JSONB, default=list)
    territory: Mapped[str | None] = mapped_column(String(128))
    owner_id: Mapped[str | None] = mapped_column(String(128))
    named_account_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    priority_tier: Mapped[str | None] = mapped_column(String(32))
    fit_score: Mapped[int] = mapped_column(Integer, default=0)
    intent_score: Mapped[int] = mapped_column(Integer, default=0)
    composite_score: Mapped[int] = mapped_column(Integer, default=0)
    last_signal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    contacts: Mapped[list["Contact"]] = relationship(back_populates="account")


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("account_id", "email", name="uq_contact_account_email"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    crm_contact_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    full_name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(255))
    seniority: Mapped[str | None] = mapped_column(String(64))
    function: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    email_status: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(64))
    linkedin_url: Mapped[str | None] = mapped_column(String(512))
    timezone: Mapped[str | None] = mapped_column(String(64))
    persona_type: Mapped[str | None] = mapped_column(String(64))
    buying_role: Mapped[str | None] = mapped_column(String(64))
    last_enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    do_not_contact_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    lawful_basis: Mapped[str | None] = mapped_column(String(64))
    source_vendor: Mapped[str | None] = mapped_column(String(128))
    source_confidence: Mapped[int] = mapped_column(Integer, default=0)
    source_url: Mapped[str | None] = mapped_column(String(1024))
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    origin_type: Mapped[str | None] = mapped_column(String(64))
    origin_id: Mapped[str | None] = mapped_column(String(128))
    source_policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    review_status: Mapped[str] = mapped_column(String(64), default="not_required")
    review_reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    account: Mapped[Account | None] = relationship(back_populates="contacts")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    source_type: Mapped[str] = mapped_column(String(64))
    source_campaign: Mapped[str | None] = mapped_column(String(128))
    source_query: Mapped[str | None] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    qualification_status: Mapped[str] = mapped_column(String(64), default="new")
    qualification_reason: Mapped[str | None] = mapped_column(Text)
    routing_status: Mapped[str] = mapped_column(String(64), default="pending")
    sequence_status: Mapped[str] = mapped_column(String(64), default="not_enrolled")
    meeting_status: Mapped[str] = mapped_column(String(64), default="none")
    opportunity_status: Mapped[str] = mapped_column(String(64), default="none")


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    signal_type: Mapped[str] = mapped_column(String(64))
    signal_source: Mapped[str] = mapped_column(String(128))
    signal_strength: Mapped[int] = mapped_column(Integer, default=0)
    signal_topic: Mapped[str | None] = mapped_column(String(255))
    signal_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    product_relevance: Mapped[str | None] = mapped_column(Text)
    recommended_play: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class EmailCandidateRecord(Base):
    __tablename__ = "email_candidates"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_email_candidates_idempotency_key"),
        Index("ix_email_candidates_origin", "origin_type", "origin_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(320), index=True)
    pattern: Mapped[str] = mapped_column(String(64))
    verification_status: Mapped[str] = mapped_column(String(64), default="pending")
    verification_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    verification_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    origin_type: Mapped[str | None] = mapped_column(String(64))
    origin_id: Mapped[str | None] = mapped_column(String(128))
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    review_status: Mapped[str] = mapped_column(String(64), default="not_required")
    review_reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Suppression(Base):
    __tablename__ = "suppressions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    domain: Mapped[str | None] = mapped_column(String(255), index=True)
    contact_id: Mapped[str | None] = mapped_column(String(128), index=True)
    channel: Mapped[str] = mapped_column(String(64), default="email")
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    actor: Mapped[str] = mapped_column(String(128), default="system")
    action: Mapped[str] = mapped_column(String(128))
    entity_type: Mapped[str] = mapped_column(String(128))
    entity_id: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    event_name: Mapped[str] = mapped_column(String(128), index=True)
    aggregate_type: Mapped[str] = mapped_column(String(128))
    aggregate_id: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
