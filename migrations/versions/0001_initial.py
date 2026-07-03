"""initial canonical schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-18
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("crm_account_id", sa.String(length=128), unique=True),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("hq_country", sa.String(length=2)),
        sa.Column("employee_count", sa.Integer()),
        sa.Column("revenue_band", sa.String(length=64)),
        sa.Column("industry", sa.String(length=128)),
        sa.Column("sub_industry", sa.String(length=128)),
        sa.Column("tech_stack", postgresql.JSONB(), nullable=False),
        sa.Column("security_stack", postgresql.JSONB(), nullable=False),
        sa.Column("intent_topics", postgresql.JSONB(), nullable=False),
        sa.Column("territory", sa.String(length=128)),
        sa.Column("owner_id", sa.String(length=128)),
        sa.Column("named_account_flag", sa.Boolean(), nullable=False),
        sa.Column("priority_tier", sa.String(length=32)),
        sa.Column("fit_score", sa.Integer(), nullable=False),
        sa.Column("intent_score", sa.Integer(), nullable=False),
        sa.Column("composite_score", sa.Integer(), nullable=False),
        sa.Column("last_signal_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_accounts_domain", "accounts", ["domain"])

    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("crm_contact_id", sa.String(length=128), unique=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255)),
        sa.Column("seniority", sa.String(length=64)),
        sa.Column("function", sa.String(length=64)),
        sa.Column("email", sa.String(length=320)),
        sa.Column("email_status", sa.String(length=64)),
        sa.Column("phone", sa.String(length=64)),
        sa.Column("linkedin_url", sa.String(length=512)),
        sa.Column("timezone", sa.String(length=64)),
        sa.Column("persona_type", sa.String(length=64)),
        sa.Column("buying_role", sa.String(length=64)),
        sa.Column("last_enriched_at", sa.DateTime(timezone=True)),
        sa.Column("do_not_contact_flag", sa.Boolean(), nullable=False),
        sa.Column("lawful_basis", sa.String(length=64)),
        sa.Column("source_vendor", sa.String(length=128)),
        sa.Column("source_confidence", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(length=1024)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "email", name="uq_contact_account_email"),
    )
    op.create_index("ix_contacts_email", "contacts", ["email"])

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
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
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_campaign", sa.String(length=128)),
        sa.Column("source_query", sa.Text()),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("qualification_status", sa.String(length=64), nullable=False),
        sa.Column("qualification_reason", sa.Text()),
        sa.Column("routing_status", sa.String(length=64), nullable=False),
        sa.Column("sequence_status", sa.String(length=64), nullable=False),
        sa.Column("meeting_status", sa.String(length=64), nullable=False),
        sa.Column("opportunity_status", sa.String(length=64), nullable=False),
    )

    op.create_table(
        "signals",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
        ),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("signal_source", sa.String(length=128), nullable=False),
        sa.Column("signal_strength", sa.Integer(), nullable=False),
        sa.Column("signal_topic", sa.String(length=255)),
        sa.Column("signal_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("product_relevance", sa.Text()),
        sa.Column("recommended_play", sa.Text()),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
    )

    op.create_table(
        "email_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("pattern", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("verification_status", sa.String(length=64), nullable=False),
        sa.Column("verification_payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_email_candidates_email", "email_candidates", ["email"])

    op.create_table(
        "suppressions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(length=320)),
        sa.Column("domain", sa.String(length=255)),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_suppressions_email", "suppressions", ["email"])
    op.create_index("ix_suppressions_domain", "suppressions", ["domain"])

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), unique=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("aggregate_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_outbox_events_event_name", "outbox_events", ["event_name"])


def downgrade() -> None:
    for table in (
        "outbox_events",
        "audit_events",
        "suppressions",
        "email_candidates",
        "signals",
        "leads",
        "contacts",
        "accounts",
    ):
        op.drop_table(table)
