"""add sequence email alerts

Revision ID: 0011_sequence_email_alerts
Revises: 0010_email_confidence
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_sequence_email_alerts"
down_revision = "0010_email_confidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sequence_email_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "enrollment_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sequence_enrollments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("send_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255)),
        sa.Column("last_error", sa.Text()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_sequence_email_alerts_idempotency_key"
        ),
    )
    op.create_index(
        "ix_sequence_email_alerts_enrollment_status",
        "sequence_email_alerts",
        ["enrollment_id", "status"],
    )
    op.create_index(
        "ix_sequence_email_alerts_due",
        "sequence_email_alerts",
        ["status", "send_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_sequence_email_alerts_due", table_name="sequence_email_alerts")
    op.drop_index(
        "ix_sequence_email_alerts_enrollment_status",
        table_name="sequence_email_alerts",
    )
    op.drop_table("sequence_email_alerts")
