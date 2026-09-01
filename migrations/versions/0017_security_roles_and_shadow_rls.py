"""provision non-bypass roles, narrow grants, and disabled CRUD policies

Revision ID: 0017_security_roles_and_shadow_rls
Revises: 0016_security_completion_schema
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_security_roles_shadow"
down_revision = "0016_security_completion_schema"
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
ROLES = (
    "ghostrecon_schema_owner",
    "ghostrecon_migration",
    "ghostrecon_gateway_security",
    "ghostrecon_event_owner",
    "ghostrecon_incident_owner",
    "ghostrecon_enrichment_owner",
    "ghostrecon_email_owner",
    "ghostrecon_crm_owner",
    "ghostrecon_sequence_owner",
    "ghostrecon_meeting_owner",
    "ghostrecon_scoring_owner",
    "ghostrecon_governance_owner",
    "ghostrecon_reporting",
    "ghostrecon_session",
    "ghostrecon_audit_writer",
    "ghostrecon_audit_reader",
    "ghostrecon_retention",
    "ghostrecon_source_fetch_worker",
    "ghostrecon_event_parser_worker",
    "ghostrecon_incident_parser_worker",
    "ghostrecon_watch_monitor_worker",
    "ghostrecon_enrichment_worker",
    "ghostrecon_email_worker",
    "ghostrecon_governance_worker",
    "ghostrecon_crm_export_worker",
    "ghostrecon_sequencing_worker",
    "ghostrecon_meeting_worker",
    "ghostrecon_scheduler",
    "ghostrecon_rls_test",
)
WRITERS = tuple(
    role
    for role in ROLES
    if role
    not in {
        "ghostrecon_schema_owner",
        "ghostrecon_migration",
        "ghostrecon_reporting",
        "ghostrecon_audit_reader",
        "ghostrecon_scheduler",
    }
)


def upgrade() -> None:
    for role in ROLES:
        op.execute(
            sa.text(
                f"""DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                  CREATE ROLE {role} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                    NOINHERIT NOBYPASSRLS;
                END IF;
                END $$"""  # noqa: S608
            )
        )
        op.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {role}"))
    for table in PROTECTED:
        op.execute(sa.text(f"REVOKE ALL ON TABLE {table} FROM PUBLIC"))
        op.execute(sa.text(f"GRANT SELECT ON TABLE {table} TO ghostrecon_reporting"))
        for role in WRITERS:
            op.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO {role}"))
        context = (
            "current_setting('ghostrecon.context_valid', true) = '1' "
            "AND current_setting('ghostrecon.permissions', true) <> '' "
            "AND current_setting('ghostrecon.calling_workload', true) <> ''"
        )
        op.execute(
            sa.text(
                f"CREATE POLICY sprint25b_{table}_select ON {table} FOR SELECT USING ({context})"
            )
        )
        op.execute(
            sa.text(
                f"CREATE POLICY sprint25b_{table}_insert ON {table} "
                f"FOR INSERT WITH CHECK ({context} AND security_classification "
                "IN ('internal', 'restricted', 'governance'))"
            )
        )
        op.execute(
            sa.text(
                f"CREATE POLICY sprint25b_{table}_update ON {table} "
                f"FOR UPDATE USING ({context}) WITH CHECK ({context} AND "
                "security_classification IN ('internal', 'restricted', 'governance'))"
            )
        )
        op.execute(
            sa.text(
                f"CREATE POLICY sprint25b_{table}_delete ON {table} "
                f"FOR DELETE USING ({context} AND current_setting("
                "'ghostrecon.permissions', true) ~ '(^|,)(security.admin|governance.decide)(,|$)')"
            )
        )


def downgrade() -> None:
    for table in reversed(PROTECTED):
        for command in ("delete", "update", "insert", "select"):
            op.execute(sa.text(f"DROP POLICY IF EXISTS sprint25b_{table}_{command} ON {table}"))
    for role in reversed(ROLES):
        op.execute(sa.text(f"REASSIGN OWNED BY {role} TO CURRENT_USER"))
        op.execute(sa.text(f"DROP OWNED BY {role}"))
        op.execute(sa.text(f"DROP ROLE IF EXISTS {role}"))
