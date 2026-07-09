"""add watchlist monitoring and discovery state

Revision ID: 0013_watchlist_monitoring
Revises: 0012_event_incident_dashboard
Create Date: 2026-07-09
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_watchlist_monitoring"
down_revision = "0012_event_incident_dashboard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "watch_targets",
        sa.Column(
            "monitoring_status",
            sa.String(length=64),
            nullable=False,
            server_default="not_run",
        ),
    )
    op.add_column(
        "watch_targets",
        sa.Column("last_monitored_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "watch_targets",
        sa.Column("next_monitoring_at", sa.DateTime(timezone=True)),
    )
    op.add_column("watch_targets", sa.Column("monitoring_error", sa.Text()))
    op.add_column(
        "watch_targets",
        sa.Column(
            "monitoring_summary",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("watch_targets", "monitoring_status", server_default=None)
    op.alter_column("watch_targets", "monitoring_summary", server_default=None)

    op.create_table(
        "watch_target_monitoring_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "watch_target_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("watch_targets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("query_summary", postgresql.JSONB(), nullable=False),
        sa.Column("result_summary", postgresql.JSONB(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_watch_target_monitoring_runs_target",
        "watch_target_monitoring_runs",
        ["watch_target_id", "started_at"],
    )
    op.create_index(
        "ix_watch_target_monitoring_runs_status",
        "watch_target_monitoring_runs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_watch_target_monitoring_runs_status",
        table_name="watch_target_monitoring_runs",
    )
    op.drop_index(
        "ix_watch_target_monitoring_runs_target",
        table_name="watch_target_monitoring_runs",
    )
    op.drop_table("watch_target_monitoring_runs")
    op.drop_column("watch_targets", "monitoring_summary")
    op.drop_column("watch_targets", "monitoring_error")
    op.drop_column("watch_targets", "next_monitoring_at")
    op.drop_column("watch_targets", "last_monitored_at")
    op.drop_column("watch_targets", "monitoring_status")
