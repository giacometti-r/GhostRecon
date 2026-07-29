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

    raw_items: Mapped[list[RawSourceItem]] = relationship(back_populates="source_definition")


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
