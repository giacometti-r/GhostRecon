"""add enrichment email and review workflows

Revision ID: 0005_enrichment_email_review
Revises: 0004_incident_intelligence
Create Date: 2026-07-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_enrichment_email_review"
down_revision = "0004_incident_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entity_resolution_cases",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("origin_type", sa.String(length=64), nullable=False),
        sa.Column("origin_id", sa.String(length=128), nullable=False),
        sa.Column("entity_kind", sa.String(length=64), nullable=False),
        sa.Column("input_name", sa.String(length=255)),
        sa.Column("input_domain", sa.String(length=255)),
        sa.Column(
            "resolved_account_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column("resolved_name", sa.String(length=255)),
        sa.Column("resolved_domain", sa.String(length=255)),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("alternatives", postgresql.JSONB(), nullable=False),
        sa.Column(
            "source_definition_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("source_definitions.id", ondelete="SET NULL"),
        ),
        sa.Column("source_item_ids", postgresql.JSONB(), nullable=False),
        sa.Column("policy_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("review_reason", sa.Text()),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_entity_resolution_cases_idempotency_key"
        ),
    )
    op.create_index(
        "ix_entity_resolution_cases_origin",
        "entity_resolution_cases",
        ["origin_type", "origin_id"],
    )
    op.create_index(
        "ix_entity_resolution_cases_status", "entity_resolution_cases", ["status"]
    )
    op.create_index(
        "ix_entity_resolution_cases_domain", "entity_resolution_cases", ["input_domain"]
    )

    op.create_table(
        "contact_enrichment_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "entity_resolution_case_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("entity_resolution_cases.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
        ),
        sa.Column("origin_type", sa.String(length=64), nullable=False),
        sa.Column("origin_id", sa.String(length=128), nullable=False),
        sa.Column("published_name", sa.String(length=255), nullable=False),
        sa.Column("organization", sa.String(length=255)),
        sa.Column("title", sa.String(length=255)),
        sa.Column("role_scope", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=255)),
        sa.Column("profile_url", sa.String(length=2048)),
        sa.Column("source_url", sa.String(length=2048)),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("eligibility_reason", sa.Text()),
        sa.Column("reuse_state", sa.String(length=64), nullable=False),
        sa.Column(
            "source_definition_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("source_definitions.id", ondelete="SET NULL"),
        ),
        sa.Column("source_item_ids", postgresql.JSONB(), nullable=False),
        sa.Column("policy_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("candidate_payload", postgresql.JSONB(), nullable=False),
        sa.Column("review_reason", sa.Text()),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_contact_enrichment_candidates_idempotency_key"
        ),
    )
    op.create_index(
        "ix_contact_enrichment_candidates_origin",
        "contact_enrichment_candidates",
        ["origin_type", "origin_id"],
    )
    op.create_index(
        "ix_contact_enrichment_candidates_status",
        "contact_enrichment_candidates",
        ["status"],
    )
    op.create_index(
        "ix_contact_enrichment_candidates_account",
        "contact_enrichment_candidates",
        ["account_id"],
    )

    op.create_table(
        "organization_email_patterns",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("pattern", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "domain", "pattern", name="uq_organization_email_patterns_domain_pattern"
        ),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_organization_email_patterns_idempotency_key"
        ),
    )
    op.create_index(
        "ix_organization_email_patterns_domain", "organization_email_patterns", ["domain"]
    )

    op.create_table(
        "review_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("candidate_type", sa.String(length=64), nullable=False),
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
        sa.Column("reason_code", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("evidence_summary", postgresql.JSONB(), nullable=False),
        sa.Column("policy_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_review_candidates_idempotency_key"),
    )
    op.create_index("ix_review_candidates_status", "review_candidates", ["status"])
    op.create_index("ix_review_candidates_type", "review_candidates", ["candidate_type"])
    op.create_index(
        "ix_review_candidates_target", "review_candidates", ["target_type", "target_id"]
    )

    _add_contact_columns()
    _add_email_candidate_columns()


def downgrade() -> None:
    _drop_email_candidate_columns()
    _drop_contact_columns()

    op.drop_index("ix_review_candidates_target", table_name="review_candidates")
    op.drop_index("ix_review_candidates_type", table_name="review_candidates")
    op.drop_index("ix_review_candidates_status", table_name="review_candidates")
    op.drop_table("review_candidates")

    op.drop_index(
        "ix_organization_email_patterns_domain", table_name="organization_email_patterns"
    )
    op.drop_table("organization_email_patterns")

    op.drop_index(
        "ix_contact_enrichment_candidates_account",
        table_name="contact_enrichment_candidates",
    )
    op.drop_index(
        "ix_contact_enrichment_candidates_status",
        table_name="contact_enrichment_candidates",
    )
    op.drop_index(
        "ix_contact_enrichment_candidates_origin",
        table_name="contact_enrichment_candidates",
    )
    op.drop_table("contact_enrichment_candidates")

    op.drop_index("ix_entity_resolution_cases_domain", table_name="entity_resolution_cases")
    op.drop_index("ix_entity_resolution_cases_status", table_name="entity_resolution_cases")
    op.drop_index("ix_entity_resolution_cases_origin", table_name="entity_resolution_cases")
    op.drop_table("entity_resolution_cases")


def _add_contact_columns() -> None:
    op.add_column(
        "contacts",
        sa.Column("source_definition_id", postgresql.UUID(as_uuid=False)),
    )
    op.add_column(
        "contacts",
        sa.Column("source_item_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column("contacts", sa.Column("origin_type", sa.String(length=64)))
    op.add_column("contacts", sa.Column("origin_id", sa.String(length=128)))
    op.add_column(
        "contacts",
        sa.Column(
            "source_policy_snapshot",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "contacts",
        sa.Column(
            "review_status",
            sa.String(length=64),
            nullable=False,
            server_default="not_required",
        ),
    )
    op.add_column("contacts", sa.Column("review_reason", sa.Text()))
    op.add_column("contacts", sa.Column("idempotency_key", sa.String(length=255)))
    op.add_column(
        "contacts", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.create_foreign_key(
        "fk_contacts_source_definition_id_source_definitions",
        "contacts",
        "source_definitions",
        ["source_definition_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_contacts_idempotency_key", "contacts", ["idempotency_key"]
    )


def _drop_contact_columns() -> None:
    op.drop_constraint("uq_contacts_idempotency_key", "contacts", type_="unique")
    op.drop_constraint(
        "fk_contacts_source_definition_id_source_definitions", "contacts", type_="foreignkey"
    )
    op.drop_column("contacts", "version")
    op.drop_column("contacts", "idempotency_key")
    op.drop_column("contacts", "review_reason")
    op.drop_column("contacts", "review_status")
    op.drop_column("contacts", "source_policy_snapshot")
    op.drop_column("contacts", "origin_id")
    op.drop_column("contacts", "origin_type")
    op.drop_column("contacts", "source_item_ids")
    op.drop_column("contacts", "source_definition_id")


def _add_email_candidate_columns() -> None:
    op.add_column(
        "email_candidates",
        sa.Column("verification_checked_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "email_candidates",
        sa.Column("source_definition_id", postgresql.UUID(as_uuid=False)),
    )
    op.add_column(
        "email_candidates",
        sa.Column("source_item_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column("email_candidates", sa.Column("origin_type", sa.String(length=64)))
    op.add_column("email_candidates", sa.Column("origin_id", sa.String(length=128)))
    op.add_column(
        "email_candidates",
        sa.Column(
            "policy_snapshot",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "email_candidates",
        sa.Column(
            "review_status",
            sa.String(length=64),
            nullable=False,
            server_default="not_required",
        ),
    )
    op.add_column("email_candidates", sa.Column("review_reason", sa.Text()))
    op.add_column("email_candidates", sa.Column("idempotency_key", sa.String(length=255)))
    op.add_column(
        "email_candidates",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_foreign_key(
        "fk_email_candidates_source_definition_id_source_definitions",
        "email_candidates",
        "source_definitions",
        ["source_definition_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_email_candidates_idempotency_key", "email_candidates", ["idempotency_key"]
    )
    op.create_index(
        "ix_email_candidates_origin", "email_candidates", ["origin_type", "origin_id"]
    )


def _drop_email_candidate_columns() -> None:
    op.drop_index("ix_email_candidates_origin", table_name="email_candidates")
    op.drop_constraint("uq_email_candidates_idempotency_key", "email_candidates", type_="unique")
    op.drop_constraint(
        "fk_email_candidates_source_definition_id_source_definitions",
        "email_candidates",
        type_="foreignkey",
    )
    op.drop_column("email_candidates", "version")
    op.drop_column("email_candidates", "idempotency_key")
    op.drop_column("email_candidates", "review_reason")
    op.drop_column("email_candidates", "review_status")
    op.drop_column("email_candidates", "policy_snapshot")
    op.drop_column("email_candidates", "origin_id")
    op.drop_column("email_candidates", "origin_type")
    op.drop_column("email_candidates", "source_item_ids")
    op.drop_column("email_candidates", "source_definition_id")
    op.drop_column("email_candidates", "verification_checked_at")
