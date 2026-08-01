from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ghostrecon.common.database import Base

from .common import utcnow


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
    human_subject: Mapped[str | None] = mapped_column(String(255), index=True)
    service_subject: Mapped[str | None] = mapped_column(String(255), index=True)
    on_behalf_of_subject: Mapped[str | None] = mapped_column(String(255))
    identity_type: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(128))
    operation: Mapped[str | None] = mapped_column(String(255), index=True)
    permission: Mapped[str | None] = mapped_column(String(128))
    decision: Mapped[str | None] = mapped_column(String(32), index=True)
    denial_category: Mapped[str | None] = mapped_column(String(64))
    assurance: Mapped[str | None] = mapped_column(String(64))
    policy_version: Mapped[str | None] = mapped_column(String(64))
    mapping_version: Mapped[str | None] = mapped_column(String(64))
    environment: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(128))
    correlation_id: Mapped[str | None] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(128))
    entity_id: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    network_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    integrity_hmac: Mapped[str | None] = mapped_column(String(64))
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
