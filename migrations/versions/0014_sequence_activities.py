"""add versioned sequence activities

Revision ID: 0014_sequence_activities
Revises: 0013_watchlist_monitoring
Create Date: 2026-07-09
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014_sequence_activities"
down_revision = "0013_watchlist_monitoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_sequence_steps_order", "sequence_steps", type_="unique")
    op.add_column(
        "sequences",
        sa.Column(
            "definition_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "sequence_steps",
        sa.Column(
            "definition_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "sequence_steps",
        sa.Column(
            "requires_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "sequence_steps",
        sa.Column(
            "step_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "sequence_enrollments",
        sa.Column(
            "definition_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.alter_column("sequence_steps", "subject_template", nullable=True)
    op.alter_column("sequence_steps", "body_template", nullable=True)
    op.create_unique_constraint(
        "uq_sequence_steps_version_order",
        "sequence_steps",
        ["sequence_id", "definition_version", "step_order"],
    )
    op.alter_column("sequences", "definition_version", server_default=None)
    op.alter_column("sequence_steps", "definition_version", server_default=None)
    op.alter_column("sequence_steps", "requires_approval", server_default=None)
    op.alter_column("sequence_steps", "step_metadata", server_default=None)
    op.alter_column("sequence_enrollments", "definition_version", server_default=None)

    op.create_table(
        "sequence_step_activities",
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
            "outbound_email_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("outbound_emails.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "meeting_handoff_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("meeting_handoffs.id", ondelete="SET NULL"),
        ),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by", sa.String(length=128)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("completed_by", sa.String(length=128)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_sequence_step_activities_idempotency_key",
        ),
    )
    op.create_index(
        "ix_sequence_step_activities_status_due",
        "sequence_step_activities",
        ["status", "due_at"],
    )
    op.create_index(
        "ix_sequence_step_activities_enrollment",
        "sequence_step_activities",
        ["enrollment_id"],
    )
    op.create_index(
        "ix_sequence_step_activities_step",
        "sequence_step_activities",
        ["sequence_step_id"],
    )
    op.alter_column("sequence_step_activities", "metadata", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_sequence_step_activities_step", table_name="sequence_step_activities")
    op.drop_index(
        "ix_sequence_step_activities_enrollment",
        table_name="sequence_step_activities",
    )
    op.drop_index(
        "ix_sequence_step_activities_status_due",
        table_name="sequence_step_activities",
    )
    op.drop_table("sequence_step_activities")
    op.drop_constraint(
        "uq_sequence_steps_version_order",
        "sequence_steps",
        type_="unique",
    )
    op.alter_column("sequence_steps", "body_template", nullable=False)
    op.alter_column("sequence_steps", "subject_template", nullable=False)
    op.drop_column("sequence_enrollments", "definition_version")
    op.drop_column("sequence_steps", "step_metadata")
    op.drop_column("sequence_steps", "requires_approval")
    op.drop_column("sequence_steps", "definition_version")
    op.drop_column("sequences", "definition_version")
    op.create_unique_constraint(
        "uq_sequence_steps_order",
        "sequence_steps",
        ["sequence_id", "step_order"],
    )
