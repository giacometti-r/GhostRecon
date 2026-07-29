from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
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

from .common import utcnow


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

    evidence_links: Mapped[list[SecurityIncidentEvidence]] = relationship(back_populates="article")


class SecurityIncident(Base):
    __tablename__ = "security_incidents"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_security_incidents_dedupe_key"),
        Index("ix_security_incidents_status", "status"),
        Index("ix_security_incidents_source_definition", "source_definition_id"),
        Index("ix_security_incidents_canonical_state", "canonical_state"),
        Index("ix_security_incidents_group", "incident_group_key"),
        Index("ix_security_incidents_primary_company", "primary_affected_company"),
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

    evidence_links: Mapped[list[SecurityIncidentEvidence]] = relationship(back_populates="incident")


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
    watch_target_id: Mapped[str] = mapped_column(ForeignKey("watch_targets.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64), default="completed")
    query_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    result_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
