"""add event and incident dashboard workflow fields

Revision ID: 0012_event_incident_dashboard
Revises: 0011_sequence_email_alerts
Create Date: 2026-07-09
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_event_incident_dashboard"
down_revision = "0011_sequence_email_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cyber_events", sa.Column("street_address", sa.String(length=255)))
    op.add_column("cyber_events", sa.Column("postcode", sa.String(length=32)))
    op.add_column("cyber_events", sa.Column("latitude", sa.Float()))
    op.add_column("cyber_events", sa.Column("longitude", sa.Float()))
    op.add_column(
        "cyber_events",
        sa.Column(
            "geocode_status",
            sa.String(length=64),
            nullable=False,
            server_default="not_required",
        ),
    )
    op.add_column("cyber_events", sa.Column("geocode_provider", sa.String(length=64)))
    op.add_column("cyber_events", sa.Column("geocode_display_name", sa.String(length=512)))
    op.add_column("cyber_events", sa.Column("geocoded_at", sa.DateTime(timezone=True)))
    op.add_column(
        "cyber_events",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.execute("UPDATE cyber_events SET event_format = 'in-person' WHERE event_format = 'physical'")
    op.execute("UPDATE cyber_events SET event_format = 'online' WHERE event_format = 'virtual'")
    op.alter_column("cyber_events", "geocode_status", server_default=None)
    op.alter_column("cyber_events", "version", server_default=None)

    op.add_column(
        "security_incidents",
        sa.Column("incident_group_key", sa.String(length=255)),
    )
    op.add_column(
        "security_incidents",
        sa.Column("primary_affected_company", sa.String(length=255)),
    )
    op.add_column(
        "security_incidents",
        sa.Column("primary_affected_domain", sa.String(length=255)),
    )
    op.add_column(
        "security_incidents",
        sa.Column(
            "evidence_urls",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.execute(
        """
        UPDATE security_incidents
        SET
            incident_group_key = COALESCE(incident_group_key, dedupe_key),
            primary_affected_company = COALESCE(
                primary_affected_company,
                affected_companies ->> 0
            ),
            primary_affected_domain = COALESCE(
                primary_affected_domain,
                affected_domains ->> 0
            )
        """
    )
    op.alter_column("security_incidents", "evidence_urls", server_default=None)
    op.create_index(
        "ix_security_incidents_group",
        "security_incidents",
        ["incident_group_key"],
    )
    op.create_index(
        "ix_security_incidents_primary_company",
        "security_incidents",
        ["primary_affected_company"],
    )


def downgrade() -> None:
    op.drop_index("ix_security_incidents_primary_company", table_name="security_incidents")
    op.drop_index("ix_security_incidents_group", table_name="security_incidents")
    op.drop_column("security_incidents", "evidence_urls")
    op.drop_column("security_incidents", "primary_affected_domain")
    op.drop_column("security_incidents", "primary_affected_company")
    op.drop_column("security_incidents", "incident_group_key")
    op.drop_column("cyber_events", "version")
    op.drop_column("cyber_events", "geocoded_at")
    op.drop_column("cyber_events", "geocode_display_name")
    op.drop_column("cyber_events", "geocode_provider")
    op.drop_column("cyber_events", "geocode_status")
    op.drop_column("cyber_events", "longitude")
    op.drop_column("cyber_events", "latitude")
    op.drop_column("cyber_events", "postcode")
    op.drop_column("cyber_events", "street_address")
