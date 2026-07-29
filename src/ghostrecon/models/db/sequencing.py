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

    steps: Mapped[list[SequenceStep]] = relationship(back_populates="sequence")
    enrollments: Mapped[list[SequenceEnrollment]] = relationship(back_populates="sequence")


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
