"""add scoring governance and review decisions

Revision ID: 0006_scoring_governance_review
Revises: 0005_enrichment_email_review
Create Date: 2026-07-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_scoring_governance_review"
down_revision = "0005_enrichment_email_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _add_review_candidate_columns()
    _add_suppression_columns()
    op.add_column(
        "security_incidents",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "candidate_scores",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("origin_type", sa.String(length=64)),
        sa.Column("origin_id", sa.String(length=128)),
        sa.Column(
            "source_definition_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("source_definitions.id", ondelete="SET NULL"),
        ),
        sa.Column("source_item_ids", postgresql.JSONB(), nullable=False),
        sa.Column("config_version", sa.String(length=64), nullable=False),
        sa.Column("component_scores", postgresql.JSONB(), nullable=False),
        sa.Column("composite_score", sa.Integer(), nullable=False),
        sa.Column("route", sa.String(length=64), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=False),
        sa.Column("policy_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("policy_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_candidate_scores_idempotency_key"),
    )
    op.create_index("ix_candidate_scores_target", "candidate_scores", ["target_type", "target_id"])
    op.create_index("ix_candidate_scores_route", "candidate_scores", ["route"])
    op.create_index("ix_candidate_scores_origin", "candidate_scores", ["origin_type", "origin_id"])

    op.create_table(
        "review_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "review_candidate_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("review_candidates.id", ondelete="SET NULL"),
        ),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("reason_code", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("evidence_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("policy_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("policy_snapshot_hash", sa.String(length=64)),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_review_decisions_idempotency_key"),
    )
    op.create_index("ix_review_decisions_candidate", "review_decisions", ["review_candidate_id"])
    op.create_index("ix_review_decisions_target", "review_decisions", ["target_type", "target_id"])
    op.create_index("ix_review_decisions_decision", "review_decisions", ["decision"])

    op.create_table(
        "crm_targets",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "review_candidate_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("review_candidates.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "review_decision_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("review_decisions.id", ondelete="SET NULL"),
        ),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("origin_type", sa.String(length=64)),
        sa.Column("origin_id", sa.String(length=128)),
        sa.Column(
            "source_definition_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("source_definitions.id", ondelete="SET NULL"),
        ),
        sa.Column("source_item_ids", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("export_status", sa.String(length=64), nullable=False),
        sa.Column("policy_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("approval_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_crm_targets_idempotency_key"),
    )
    op.create_index("ix_crm_targets_target", "crm_targets", ["target_type", "target_id"])
    op.create_index("ix_crm_targets_status", "crm_targets", ["status"])
    op.create_index("ix_crm_targets_origin", "crm_targets", ["origin_type", "origin_id"])


def downgrade() -> None:
    op.drop_index("ix_crm_targets_origin", table_name="crm_targets")
    op.drop_index("ix_crm_targets_status", table_name="crm_targets")
    op.drop_index("ix_crm_targets_target", table_name="crm_targets")
    op.drop_table("crm_targets")

    op.drop_index("ix_review_decisions_decision", table_name="review_decisions")
    op.drop_index("ix_review_decisions_target", table_name="review_decisions")
    op.drop_index("ix_review_decisions_candidate", table_name="review_decisions")
    op.drop_table("review_decisions")

    op.drop_index("ix_candidate_scores_origin", table_name="candidate_scores")
    op.drop_index("ix_candidate_scores_route", table_name="candidate_scores")
    op.drop_index("ix_candidate_scores_target", table_name="candidate_scores")
    op.drop_table("candidate_scores")

    op.drop_column("security_incidents", "version")
    _drop_suppression_columns()
    _drop_review_candidate_columns()


def _add_review_candidate_columns() -> None:
    op.add_column("review_candidates", sa.Column("policy_snapshot_hash", sa.String(length=64)))
    op.add_column("review_candidates", sa.Column("sla_due_at", sa.DateTime(timezone=True)))


def _drop_review_candidate_columns() -> None:
    op.drop_column("review_candidates", "sla_due_at")
    op.drop_column("review_candidates", "policy_snapshot_hash")


def _add_suppression_columns() -> None:
    op.add_column("suppressions", sa.Column("contact_id", sa.String(length=128)))
    op.add_column("suppressions", sa.Column("target_type", sa.String(length=64)))
    op.add_column("suppressions", sa.Column("target_id", sa.String(length=128)))
    op.add_column("suppressions", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.add_column(
        "suppressions",
        sa.Column("policy_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.add_column("suppressions", sa.Column("idempotency_key", sa.String(length=255)))
    op.create_index("ix_suppressions_contact_id", "suppressions", ["contact_id"])
    op.create_unique_constraint(
        "uq_suppressions_idempotency_key", "suppressions", ["idempotency_key"]
    )


def _drop_suppression_columns() -> None:
    op.drop_constraint("uq_suppressions_idempotency_key", "suppressions", type_="unique")
    op.drop_index("ix_suppressions_contact_id", table_name="suppressions")
    op.drop_column("suppressions", "idempotency_key")
    op.drop_column("suppressions", "policy_snapshot")
    op.drop_column("suppressions", "expires_at")
    op.drop_column("suppressions", "target_id")
    op.drop_column("suppressions", "target_type")
    op.drop_column("suppressions", "contact_id")
