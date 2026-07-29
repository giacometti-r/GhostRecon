"""add sequence runtime tables

Revision ID: 0008_sequence_runtime
Revises: 0007_crm_export_batches
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_sequence_runtime"
down_revision = "0007_crm_export_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sequences",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_id", sa.String(length=128)),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("rate_limit_policy", postgresql.JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_sequences_idempotency_key"),
    )
    op.create_index("ix_sequences_status_owner", "sequences", ["status", "owner_id"])

    op.create_table(
        "sequence_steps",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "sequence_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sequences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("delay_seconds", sa.Integer(), nullable=False),
        sa.Column("subject_template", sa.String(length=512), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("sequence_id", "step_order", name="uq_sequence_steps_order"),
    )
    op.create_index(
        "ix_sequence_steps_sequence_order",
        "sequence_steps",
        ["sequence_id", "step_order"],
    )

    op.create_table(
        "sequence_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "sequence_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sequences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "crm_target_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("crm_targets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("approval_actor", sa.String(length=128), nullable=False),
        sa.Column("approval_reason", sa.Text(), nullable=False),
        sa.Column("current_step_order", sa.Integer(), nullable=False),
        sa.Column("next_step_at", sa.DateTime(timezone=True)),
        sa.Column("pause_reason", sa.Text()),
        sa.Column("policy_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("idempotency_key", name="uq_sequence_enrollments_idempotency_key"),
    )
    op.create_index(
        "ix_sequence_enrollments_status_next",
        "sequence_enrollments",
        ["status", "next_step_at"],
    )
    op.create_index(
        "ix_sequence_enrollments_contact_status",
        "sequence_enrollments",
        ["contact_id", "status"],
    )

    op.create_table(
        "outbound_emails",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "enrollment_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sequence_enrollments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sequence_step_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sequence_steps.id"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("to_email", sa.String(length=320), nullable=False),
        sa.Column("from_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255)),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("retry_after_seconds", sa.Integer()),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_outbound_emails_idempotency_key"),
    )
    op.create_index(
        "ix_outbound_emails_enrollment_status",
        "outbound_emails",
        ["enrollment_id", "status"],
    )
    op.create_index("ix_outbound_emails_sent", "outbound_emails", ["channel", "sent_at"])
    op.create_index("ix_outbound_emails_to_email", "outbound_emails", ["to_email"])

    op.create_table(
        "inbound_email_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "enrollment_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sequence_enrollments.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "outbound_email_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("outbound_emails.id", ondelete="SET NULL"),
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("from_email", sa.String(length=320)),
        sa.Column("to_email", sa.String(length=320)),
        sa.Column("message_id", sa.String(length=255)),
        sa.Column("provider_payload", postgresql.JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_inbound_email_events_idempotency_key"),
    )
    op.create_index(
        "ix_inbound_email_events_type_occurred",
        "inbound_email_events",
        ["event_type", "occurred_at"],
    )
    op.create_index("ix_inbound_email_events_from_email", "inbound_email_events", ["from_email"])

    op.create_table(
        "sequence_suppression_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "enrollment_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sequence_enrollments.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "suppression_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("suppressions.id", ondelete="SET NULL"),
        ),
        sa.Column("email", sa.String(length=320)),
        sa.Column("domain", sa.String(length=255)),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column(
            "source_event_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("inbound_email_events.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_sequence_suppression_events_email",
        "sequence_suppression_events",
        ["email"],
    )
    op.create_index(
        "ix_sequence_suppression_events_enrollment",
        "sequence_suppression_events",
        ["enrollment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sequence_suppression_events_enrollment",
        table_name="sequence_suppression_events",
    )
    op.drop_index("ix_sequence_suppression_events_email", table_name="sequence_suppression_events")
    op.drop_table("sequence_suppression_events")

    op.drop_index("ix_inbound_email_events_from_email", table_name="inbound_email_events")
    op.drop_index("ix_inbound_email_events_type_occurred", table_name="inbound_email_events")
    op.drop_table("inbound_email_events")

    op.drop_index("ix_outbound_emails_to_email", table_name="outbound_emails")
    op.drop_index("ix_outbound_emails_sent", table_name="outbound_emails")
    op.drop_index("ix_outbound_emails_enrollment_status", table_name="outbound_emails")
    op.drop_table("outbound_emails")

    op.drop_index(
        "ix_sequence_enrollments_contact_status",
        table_name="sequence_enrollments",
    )
    op.drop_index("ix_sequence_enrollments_status_next", table_name="sequence_enrollments")
    op.drop_table("sequence_enrollments")

    op.drop_index("ix_sequence_steps_sequence_order", table_name="sequence_steps")
    op.drop_table("sequence_steps")

    op.drop_index("ix_sequences_status_owner", table_name="sequences")
    op.drop_table("sequences")
