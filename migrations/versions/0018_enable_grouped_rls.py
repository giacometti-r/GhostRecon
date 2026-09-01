"""enable row security for classified tables

Revision ID: 0018_enable_grouped_rls
Revises: 0017_security_roles_and_shadow_rls
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0018_enable_grouped_rls"
down_revision = "0017_security_roles_shadow"
branch_labels = None
depends_on = None

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
    for table in PROTECTED:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    for table in reversed(PROTECTED):
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
