from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ghostrecon.common.database import Base

from .common import utcnow


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
