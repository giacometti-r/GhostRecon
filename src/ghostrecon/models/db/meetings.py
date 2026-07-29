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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ghostrecon.common.database import Base

from .common import utcnow


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

    prep_packets: Mapped[list[MeetingPrepPacket]] = relationship(back_populates="meeting")
    follow_up_tasks: Mapped[list[MeetingFollowUpTask]] = relationship(back_populates="meeting")


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
