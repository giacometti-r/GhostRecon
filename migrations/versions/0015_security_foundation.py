"""add Sprint 25 identity, session, replay, audit, and initial RLS foundation

Revision ID: 0015_security_foundation
Revises: 0014_sequence_activities
Create Date: 2026-07-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015_security_foundation"
down_revision = "0014_sequence_activities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_principals",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("actor_label", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "role_ceiling",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("mapping_version", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_security_principal"),
    )
    op.create_table(
        "security_role_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "principal_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("security_principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("granted_by_subject", sa.String(255), nullable=False),
        sa.Column("reason", sa.String(512), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("principal_id", "role", name="uq_security_role_binding"),
    )
    op.create_index(
        "ix_security_role_bindings_principal_id",
        "security_role_bindings",
        ["principal_id"],
    )
    op.create_table(
        "security_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "principal_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("security_principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("identifier_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_digest", sa.String(64), nullable=False),
        sa.Column("authentication_method", sa.String(128), nullable=False),
        sa.Column("assurance", sa.String(64), nullable=False),
        sa.Column("authenticated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_roles_refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotate_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remembered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revocation_reason", sa.String(255)),
        sa.Column("mapping_version", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_security_sessions_principal_id", "security_sessions", ["principal_id"])
    op.create_index("ix_security_sessions_revoked_at", "security_sessions", ["revoked_at"])
    op.create_table(
        "security_emergency_grants",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "principal_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("security_principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("permissions", postgresql.JSONB(), nullable=False),
        sa.Column("reason", sa.String(512), nullable=False),
        sa.Column("approver_evidence", sa.String(512), nullable=False),
        sa.Column("assurance", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_security_emergency_grants_principal_id",
        "security_emergency_grants",
        ["principal_id"],
    )
    op.create_table(
        "security_replay_markers",
        sa.Column("namespace", sa.String(64), primary_key=True),
        sa.Column("jti_digest", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_security_replay_markers_expires_at",
        "security_replay_markers",
        ["expires_at"],
    )
    op.create_table(
        "security_policy_versions",
        sa.Column("version", sa.String(64), primary_key=True),
        sa.Column("sequence", sa.Integer(), nullable=False, unique=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_by_subject", sa.String(255), nullable=False),
    )

    audit_columns = (
        sa.Column("human_subject", sa.String(255)),
        sa.Column("service_subject", sa.String(255)),
        sa.Column("on_behalf_of_subject", sa.String(255)),
        sa.Column("identity_type", sa.String(32)),
        sa.Column("operation", sa.String(255)),
        sa.Column("permission", sa.String(128)),
        sa.Column("decision", sa.String(32)),
        sa.Column("denial_category", sa.String(64)),
        sa.Column("assurance", sa.String(64)),
        sa.Column("policy_version", sa.String(64)),
        sa.Column("mapping_version", sa.String(64)),
        sa.Column("environment", sa.String(64)),
        sa.Column("request_id", sa.String(128)),
        sa.Column("correlation_id", sa.String(128)),
        sa.Column(
            "network_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("integrity_hmac", sa.String(64)),
    )
    for column in audit_columns:
        op.add_column("audit_events", column)
    for column in ("human_subject", "service_subject", "operation", "decision", "correlation_id"):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column])

    # Policies intentionally default-deny when transaction context is absent.
    op.execute(
        """
        CREATE POLICY security_principal_self_select ON security_principals
        FOR SELECT USING (
          subject = current_setting('ghostrecon.represented_subject', true)
          OR current_setting('ghostrecon.permissions', true)
             ~ '(^|,)security\\.admin(,|$)'
        )
        """
    )
    op.execute(
        """
        CREATE POLICY security_session_self_select ON security_sessions
        FOR SELECT USING (
          principal_id IN (
            SELECT id FROM security_principals
            WHERE subject = current_setting('ghostrecon.represented_subject', true)
          )
          OR current_setting('ghostrecon.permissions', true)
             ~ '(^|,)security\\.admin(,|$)'
        )
        """
    )
    op.execute(
        """
        CREATE POLICY audit_reader_select ON audit_events
        FOR SELECT USING (
          current_setting('ghostrecon.permissions', true)
          ~ '(^|,)security\\.audit\\.read(,|$)'
        )
        """
    )


def downgrade() -> None:
    for table, policy in (
        ("audit_events", "audit_reader_select"),
        ("security_sessions", "security_session_self_select"),
        ("security_principals", "security_principal_self_select"),
    ):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"'))
    for column in (
        "correlation_id",
        "decision",
        "operation",
        "service_subject",
        "human_subject",
    ):
        op.drop_index(f"ix_audit_events_{column}", table_name="audit_events")
    for column in (
        "integrity_hmac",
        "network_metadata",
        "correlation_id",
        "request_id",
        "environment",
        "mapping_version",
        "policy_version",
        "assurance",
        "denial_category",
        "decision",
        "permission",
        "operation",
        "identity_type",
        "on_behalf_of_subject",
        "service_subject",
        "human_subject",
    ):
        op.drop_column("audit_events", column)
    op.drop_table("security_policy_versions")
    op.drop_index("ix_security_replay_markers_expires_at", table_name="security_replay_markers")
    op.drop_table("security_replay_markers")
    op.drop_index(
        "ix_security_emergency_grants_principal_id", table_name="security_emergency_grants"
    )
    op.drop_table("security_emergency_grants")
    op.drop_index("ix_security_sessions_revoked_at", table_name="security_sessions")
    op.drop_index("ix_security_sessions_principal_id", table_name="security_sessions")
    op.drop_table("security_sessions")
    op.drop_index("ix_security_role_bindings_principal_id", table_name="security_role_bindings")
    op.drop_table("security_role_bindings")
    op.drop_table("security_principals")
