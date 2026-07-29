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

    contacts: Mapped[list[Contact]] = relationship(back_populates="account")


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
