"""add intelligence source registry

Revision ID: 0002_source_registry
Revises: 0001_initial
Create Date: 2026-06-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_source_registry"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("adapter_type", sa.String(length=64), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("owner", sa.String(length=128)),
        sa.Column("query_scope", postgresql.JSONB(), nullable=False),
        sa.Column("credentials_ref", sa.String(length=255)),
        sa.Column("rate_limit_policy", postgresql.JSONB(), nullable=False),
        sa.Column("polling_interval_seconds", sa.Integer()),
        sa.Column("freshness_slo_seconds", sa.Integer(), nullable=False),
        sa.Column("checkpoint_strategy", sa.String(length=64)),
        sa.Column("checkpoint_state", postgresql.JSONB(), nullable=False),
        sa.Column("retry_budget", sa.Integer(), nullable=False),
        sa.Column("policy_state", sa.String(length=64), nullable=False),
        sa.Column("policy_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("policy_reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("participant_reuse_state", sa.String(length=64), nullable=False),
        sa.Column("participant_reuse_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("content_storage_policy", sa.String(length=64), nullable=False),
        sa.Column("default_language", sa.String(length=16)),
        sa.Column("expected_timezone", sa.String(length=64)),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("operating_state", sa.String(length=64), nullable=False),
        sa.Column("last_fetch_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_source_definitions_name"),
    )
    op.create_index(
        "ix_source_definitions_kind_enabled",
        "source_definitions",
        ["source_kind", "enabled"],
    )
    op.create_index("ix_source_definitions_source_kind", "source_definitions", ["source_kind"])

    op.create_table(
        "raw_source_items",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "source_definition_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("source_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=512)),
        sa.Column("original_url", sa.String(length=2048)),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("original_language", sa.String(length=16)),
        sa.Column("source_timezone", sa.String(length=64)),
        sa.Column("raw_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("permitted_excerpt", sa.Text()),
        sa.Column("parse_status", sa.String(length=64), nullable=False),
        sa.Column("duplicate_state", sa.String(length=64), nullable=False),
        sa.Column("quarantine_reason", sa.Text()),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_raw_source_items_idempotency_key"),
        sa.UniqueConstraint(
            "source_definition_id",
            "external_id",
            name="uq_raw_source_items_source_external_id",
        ),
        sa.UniqueConstraint(
            "source_definition_id",
            "canonical_url",
            "content_hash",
            name="uq_raw_source_items_source_url_hash",
        ),
    )
    op.create_index(
        "ix_raw_source_items_source_retrieved",
        "raw_source_items",
        ["source_definition_id", "retrieved_at"],
    )
    op.create_index("ix_raw_source_items_parse_status", "raw_source_items", ["parse_status"])


def downgrade() -> None:
    op.drop_table("raw_source_items")
    op.drop_index("ix_source_definitions_source_kind", table_name="source_definitions")
    op.drop_index("ix_source_definitions_kind_enabled", table_name="source_definitions")
    op.drop_table("source_definitions")
