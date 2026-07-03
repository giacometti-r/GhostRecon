from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    city: Mapped[str | None] = mapped_column(String(128))
    region: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(2))
    virtual_url: Mapped[str | None] = mapped_column(String(2048))
    topics: Mapped[list[object]] = mapped_column(JSONB, default=list)
    organizers: Mapped[list[object]] = mapped_column(JSONB, default=list)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    canonical_state: Mapped[str] = mapped_column(String(64), default="canonical")
    dedupe_key: Mapped[str] = mapped_column(String(255))
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
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
    corroboration_method: Mapped[str] = mapped_column(String(64), default="none")
    analyst_decision_ref: Mapped[str | None] = mapped_column(String(255))
    canonical_state: Mapped[str] = mapped_column(String(64), default="canonical")
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
    origin_incident_id: Mapped[str | None] = mapped_column(
        ForeignKey("security_incidents.id", ondelete="SET NULL")
    )
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    version: Mapped[int] = mapped_column(Integer, default=1)
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

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(320), index=True)
    pattern: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[int] = mapped_column(Integer)
    verification_status: Mapped[str] = mapped_column(String(64), default="pending")
    verification_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Suppression(Base):
    __tablename__ = "suppressions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    domain: Mapped[str | None] = mapped_column(String(255), index=True)
    channel: Mapped[str] = mapped_column(String(64), default="email")
    reason: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
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
