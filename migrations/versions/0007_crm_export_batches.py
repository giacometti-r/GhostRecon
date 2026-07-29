"""add crm export batches and items

Revision ID: 0007_crm_export_batches
Revises: 0006_scoring_governance_review
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_crm_export_batches"
down_revision = "0006_scoring_governance_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_export_batches",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=128)),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("crm_target_ids", postgresql.JSONB(), nullable=False),
        sa.Column("selection_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("counts", postgresql.JSONB(), nullable=False),
        sa.Column("reconciliation_summary", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_crm_export_batches_idempotency_key"),
    )
    op.create_index(
        "ix_crm_export_batches_provider_status",
        "crm_export_batches",
        ["provider", "status"],
    )
    op.create_index(
        "ix_crm_export_batches_requested_by",
        "crm_export_batches",
        ["requested_by"],
    )

    op.create_table(
        "crm_export_items",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("crm_export_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "crm_target_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("crm_targets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("dependency_item_ids", postgresql.JSONB(), nullable=False),
        sa.Column("provider_object", sa.String(length=128), nullable=False),
        sa.Column("provider_record_id", sa.String(length=255)),
        sa.Column("provider_list_id", sa.String(length=255)),
        sa.Column("provider_list_entry_id", sa.String(length=255)),
        sa.Column("stable_match_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("retry_after_seconds", sa.Integer()),
        sa.Column("reconciliation_state", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "batch_id",
            "crm_target_id",
            name="uq_crm_export_items_batch_target",
        ),
    )
    op.create_index(
        "ix_crm_export_items_batch_status",
        "crm_export_items",
        ["batch_id", "status"],
    )
    op.create_index(
        "ix_crm_export_items_target",
        "crm_export_items",
        ["target_type", "target_id"],
    )
    op.create_index(
        "ix_crm_export_items_provider_record",
        "crm_export_items",
        ["provider_object", "provider_record_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_crm_export_items_provider_record", table_name="crm_export_items")
    op.drop_index("ix_crm_export_items_target", table_name="crm_export_items")
    op.drop_index("ix_crm_export_items_batch_status", table_name="crm_export_items")
    op.drop_table("crm_export_items")

    op.drop_index("ix_crm_export_batches_requested_by", table_name="crm_export_batches")
    op.drop_index("ix_crm_export_batches_provider_status", table_name="crm_export_batches")
    op.drop_table("crm_export_batches")
