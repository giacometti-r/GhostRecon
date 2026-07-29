from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ghostrecon.common.database import Base

from .common import utcnow


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

    participants: Mapped[list[EventParticipant]] = relationship(back_populates="event")


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
