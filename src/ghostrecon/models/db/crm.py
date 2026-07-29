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

    items: Mapped[list[CrmExportItem]] = relationship(back_populates="batch")


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
