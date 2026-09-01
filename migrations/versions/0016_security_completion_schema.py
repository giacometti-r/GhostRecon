"""add provider role state and conservative row-security classification

Revision ID: 0016_security_completion_schema
Revises: 0015_security_foundation
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016_security_completion_schema"
down_revision = "0015_security_foundation"
branch_labels = None
depends_on = None

EXCLUDED = ("cyber_events", "organization_email_patterns")
PROTECTED = (
    "accounts",
    "audit_events",
    "candidate_scores",
    "contact_enrichment_candidates",
    "contacts",
    "crm_export_batches",
    "crm_export_items",
    "crm_targets",
    "email_candidates",
    "entity_resolution_cases",
    "event_participants",
    "inbound_email_events",
    "leads",
    "meeting_follow_up_tasks",
    "meeting_handoffs",
    "meeting_prep_packets",
    "news_articles",
    "outbound_emails",
    "outbox_events",
    "raw_source_items",
    "review_candidates",
    "review_decisions",
    "security_emergency_grants",
    "security_incident_evidence",
    "security_incidents",
    "security_policy_versions",
    "security_principals",
    "security_replay_markers",
    "security_role_bindings",
    "security_sessions",
    "sequence_email_alerts",
    "sequence_enrollments",
    "sequence_step_activities",
    "sequence_steps",
    "sequence_suppression_events",
    "sequences",
    "signals",
    "source_definitions",
    "suppressions",
    "watch_target_monitoring_runs",
    "watch_targets",
)


def upgrade() -> None:
    op.add_column(
        "security_sessions",
        sa.Column(
            "provider_roles",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    for table in PROTECTED:
        op.add_column(
            table,
            sa.Column(
                "security_classification",
                sa.String(32),
                nullable=False,
                server_default="restricted",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "scope_policy_version",
                sa.String(64),
                nullable=False,
                server_default="sprint25b.v1",
            ),
        )
        op.create_index(f"ix_{table}_security_classification", table, ["security_classification"])
    for table in (
        "accounts",
        "security_incidents",
        "watch_targets",
        "sequences",
        "meeting_handoffs",
    ):
        op.add_column(table, sa.Column("owner_subject", sa.String(255)))
        op.create_index(f"ix_{table}_owner_subject", table, ["owner_subject"])
    for table in ("review_candidates", "crm_targets", "meeting_follow_up_tasks"):
        op.add_column(table, sa.Column("assignee_subject", sa.String(255)))
        op.create_index(f"ix_{table}_assignee_subject", table, ["assignee_subject"])
    for table in (
        "raw_source_items",
        "outbox_events",
        "watch_target_monitoring_runs",
        "crm_export_items",
        "sequence_step_activities",
    ):
        op.add_column(table, sa.Column("owning_workload", sa.String(128)))
        op.create_index(f"ix_{table}_owning_workload", table, ["owning_workload"])


def downgrade() -> None:
    for table in (
        "sequence_step_activities",
        "crm_export_items",
        "watch_target_monitoring_runs",
        "outbox_events",
        "raw_source_items",
    ):
        op.drop_index(f"ix_{table}_owning_workload", table_name=table)
        op.drop_column(table, "owning_workload")
    for table in ("meeting_follow_up_tasks", "crm_targets", "review_candidates"):
        op.drop_index(f"ix_{table}_assignee_subject", table_name=table)
        op.drop_column(table, "assignee_subject")
    for table in (
        "meeting_handoffs",
        "sequences",
        "watch_targets",
        "security_incidents",
        "accounts",
    ):
        op.drop_index(f"ix_{table}_owner_subject", table_name=table)
        op.drop_column(table, "owner_subject")
    for table in reversed(PROTECTED):
        op.drop_index(f"ix_{table}_security_classification", table_name=table)
        op.drop_column(table, "scope_policy_version")
        op.drop_column(table, "security_classification")
    op.drop_column("security_sessions", "provider_roles")
