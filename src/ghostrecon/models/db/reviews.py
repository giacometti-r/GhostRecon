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


class ReviewCandidate(Base):
    __tablename__ = "review_candidates"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_review_candidates_idempotency_key"),
        Index("ix_review_candidates_status", "status"),
        Index("ix_review_candidates_type", "candidate_type"),
        Index("ix_review_candidates_target", "target_type", "target_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    candidate_type: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(128))
    origin_type: Mapped[str | None] = mapped_column(String(64))
    origin_id: Mapped[str | None] = mapped_column(String(128))
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(64), default="open")
    reason_code: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    policy_snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CandidateScore(Base):
    __tablename__ = "candidate_scores"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_candidate_scores_idempotency_key"),
        Index("ix_candidate_scores_target", "target_type", "target_id"),
        Index("ix_candidate_scores_route", "route"),
        Index("ix_candidate_scores_origin", "origin_type", "origin_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(128))
    origin_type: Mapped[str | None] = mapped_column(String(64))
    origin_id: Mapped[str | None] = mapped_column(String(128))
    source_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_definitions.id", ondelete="SET NULL")
    )
    source_item_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    config_version: Mapped[str] = mapped_column(String(64))
    component_scores: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    composite_score: Mapped[int] = mapped_column(Integer, default=0)
    route: Mapped[str] = mapped_column(String(64))
    reasons: Mapped[list[object]] = mapped_column(JSONB, default=list)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    policy_snapshot_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_review_decisions_idempotency_key"),
        Index("ix_review_decisions_candidate", "review_candidate_id"),
        Index("ix_review_decisions_target", "target_type", "target_id"),
        Index("ix_review_decisions_decision", "decision"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    review_candidate_id: Mapped[str | None] = mapped_column(
        ForeignKey("review_candidates.id", ondelete="SET NULL")
    )
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(128))
    decision: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(128))
    reason_code: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    policy_snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
