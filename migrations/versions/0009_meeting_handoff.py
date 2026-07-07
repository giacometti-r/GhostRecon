"""add meeting handoff tables

Revision ID: 0009_meeting_handoff
Revises: 0008_sequence_runtime
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_meeting_handoff"
down_revision = "0008_sequence_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meeting_handoffs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "crm_target_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("crm_targets.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "sequence_enrollment_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sequence_enrollments.id", ondelete="SET NULL"),
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
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("location", sa.String(length=512)),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("attendees", postgresql.JSONB(), nullable=False),
        sa.Column("calendar_provider", sa.String(length=64), nullable=False),
        sa.Column("calendar_id", sa.String(length=512)),
        sa.Column("provider_event_id", sa.String(length=512)),
        sa.Column("provider_html_link", sa.String(length=2048)),
        sa.Column("provider_payload", postgresql.JSONB(), nullable=False),
        sa.Column("outcome_status", sa.String(length=64)),
        sa.Column("outcome_notes", sa.Text()),
        sa.Column("next_steps", postgresql.JSONB(), nullable=False),
        sa.Column("crm_sync_status", sa.String(length=64), nullable=False),
        sa.Column("crm_sync_error", sa.Text()),
        sa.Column("crm_retry_after_seconds", sa.Integer()),
        sa.Column("policy_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_meeting_handoffs_idempotency_key"),
    )
    op.create_index(
        "ix_meeting_handoffs_status_start",
        "meeting_handoffs",
        ["status", "start_at"],
    )
    op.create_index("ix_meeting_handoffs_crm_target", "meeting_handoffs", ["crm_target_id"])
    op.create_index(
        "ix_meeting_handoffs_contact_status",
        "meeting_handoffs",
        ["contact_id", "status"],
    )
    op.create_index(
        "ix_meeting_handoffs_provider_event",
        "meeting_handoffs",
        ["calendar_provider", "provider_event_id"],
    )

    op.create_table(
        "meeting_prep_packets",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "meeting_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("meeting_handoffs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_summary", sa.Text(), nullable=False),
        sa.Column("stakeholder_map", postgresql.JSONB(), nullable=False),
        sa.Column("likely_security_priorities", postgresql.JSONB(), nullable=False),
        sa.Column("suggested_questions", postgresql.JSONB(), nullable=False),
        sa.Column("risks", postgresql.JSONB(), nullable=False),
        sa.Column("source_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("generated_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_meeting_prep_packets_idempotency_key"
        ),
    )
    op.create_index(
        "ix_meeting_prep_packets_meeting", "meeting_prep_packets", ["meeting_id"]
    )

    op.create_table(
        "meeting_follow_up_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "meeting_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("meeting_handoffs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("owner", sa.String(length=128)),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("crm_sync_status", sa.String(length=64), nullable=False),
        sa.Column("provider_task_id", sa.String(length=512)),
        sa.Column("last_error", sa.Text()),
        sa.Column("idempotency_key", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_meeting_follow_up_tasks_idempotency_key"
        ),
    )
    op.create_index(
        "ix_meeting_follow_up_tasks_meeting", "meeting_follow_up_tasks", ["meeting_id"]
    )
    op.create_index(
        "ix_meeting_follow_up_tasks_status_due",
        "meeting_follow_up_tasks",
        ["status", "due_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_meeting_follow_up_tasks_status_due", table_name="meeting_follow_up_tasks"
    )
    op.drop_index("ix_meeting_follow_up_tasks_meeting", table_name="meeting_follow_up_tasks")
    op.drop_table("meeting_follow_up_tasks")

    op.drop_index("ix_meeting_prep_packets_meeting", table_name="meeting_prep_packets")
    op.drop_table("meeting_prep_packets")

    op.drop_index("ix_meeting_handoffs_provider_event", table_name="meeting_handoffs")
    op.drop_index("ix_meeting_handoffs_contact_status", table_name="meeting_handoffs")
    op.drop_index("ix_meeting_handoffs_crm_target", table_name="meeting_handoffs")
    op.drop_index("ix_meeting_handoffs_status_start", table_name="meeting_handoffs")
    op.drop_table("meeting_handoffs")
