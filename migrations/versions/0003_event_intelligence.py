"""add event intelligence runtime

Revision ID: 0003_event_intelligence
Revises: 0002_source_registry
Create Date: 2026-07-03
"""

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_event_intelligence"
down_revision = "0002_source_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cyber_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("event_series_key", sa.String(length=128), nullable=False),
        sa.Column("external_id", sa.String(length=512)),
        sa.Column("canonical_url", sa.String(length=2048)),
        sa.Column("original_start", sa.String(length=128)),
        sa.Column("original_end", sa.String(length=128)),
        sa.Column("source_timezone", sa.String(length=64)),
        sa.Column("iana_timezone", sa.String(length=64)),
        sa.Column("timezone_status", sa.String(length=64), nullable=False),
        sa.Column("starts_at_utc", sa.DateTime(timezone=True)),
        sa.Column("ends_at_utc", sa.DateTime(timezone=True)),
        sa.Column("event_format", sa.String(length=64), nullable=False),
        sa.Column("venue_name", sa.String(length=255)),
        sa.Column("city", sa.String(length=128)),
        sa.Column("region", sa.String(length=128)),
        sa.Column("country", sa.String(length=2)),
        sa.Column("virtual_url", sa.String(length=2048)),
        sa.Column("topics", postgresql.JSONB(), nullable=False),
        sa.Column("organizers", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("canonical_state", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column(
            "source_definition_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("source_definitions.id", ondelete="SET NULL"),
        ),
        sa.Column("source_item_ids", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dedupe_key", name="uq_cyber_events_dedupe_key"),
    )
    op.create_index(
        "ix_cyber_events_series_start", "cyber_events", ["event_series_key", "starts_at_utc"]
    )
    op.create_index("ix_cyber_events_source_definition", "cyber_events", ["source_definition_id"])
    op.create_index("ix_cyber_events_canonical_state", "cyber_events", ["canonical_state"])

    op.create_table(
        "event_participants",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "cyber_event_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("cyber_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_definition_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("source_definitions.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "source_item_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("raw_source_items.id", ondelete="SET NULL"),
        ),
        sa.Column("source_participant_id", sa.String(length=512)),
        sa.Column("published_name", sa.String(length=255), nullable=False),
        sa.Column("organization", sa.String(length=255)),
        sa.Column("published_role", sa.String(length=255)),
        sa.Column("participant_type", sa.String(length=64), nullable=False),
        sa.Column("profile_url", sa.String(length=2048)),
        sa.Column("reuse_state", sa.String(length=64), nullable=False),
        sa.Column("reuse_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("contact_extraction_allowed", sa.Boolean(), nullable=False),
        sa.Column("crm_export_allowed", sa.Boolean(), nullable=False),
        sa.Column("resolution_confidence", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dedupe_key", name="uq_event_participants_dedupe_key"),
    )
    op.create_index("ix_event_participants_event", "event_participants", ["cyber_event_id"])
    op.create_index("ix_event_participants_source_item", "event_participants", ["source_item_id"])
    op.create_index("ix_event_participants_reuse", "event_participants", ["reuse_state"])

    _seed_event_sources()


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM source_definitions "
            "WHERE name IN ("
            "'DEF CON official events', "
            "'Black Hat upcoming events', "
            "'Security BSides events', "
            "'OWASP events', "
            "'FIRST events'"
            ")"
        )
    )
    op.drop_index("ix_event_participants_reuse", table_name="event_participants")
    op.drop_index("ix_event_participants_source_item", table_name="event_participants")
    op.drop_index("ix_event_participants_event", table_name="event_participants")
    op.drop_table("event_participants")
    op.drop_index("ix_cyber_events_canonical_state", table_name="cyber_events")
    op.drop_index("ix_cyber_events_source_definition", table_name="cyber_events")
    op.drop_index("ix_cyber_events_series_start", table_name="cyber_events")
    op.drop_table("cyber_events")


def _seed_event_sources() -> None:
    now = datetime.now(UTC)
    sources = [
        {
            "name": "DEF CON official events",
            "adapter_type": "http_page",
            "base_url": "https://defcon.org/",
            "query_scope": {"event_series_key": "def-con", "official": True},
        },
        {
            "name": "Black Hat upcoming events",
            "adapter_type": "http_page",
            "base_url": "https://blackhat.com/upcoming.html",
            "query_scope": {"event_series_key": "black-hat", "official": True},
        },
        {
            "name": "Security BSides events",
            "adapter_type": "http_page",
            "base_url": "https://bsides.org/events/",
            "query_scope": {"event_series_key": "bsides", "official": True},
        },
        {
            "name": "OWASP events",
            "adapter_type": "http_page",
            "base_url": "https://owasp.org/events/",
            "query_scope": {"event_series_key": "owasp", "official": True},
        },
        {
            "name": "FIRST events",
            "adapter_type": "http_page",
            "base_url": "https://www.first.org/events/",
            "query_scope": {"event_series_key": "first", "official": True},
        },
    ]
    table = sa.table(
        "source_definitions",
        sa.column("id"),
        sa.column("name"),
        sa.column("source_kind"),
        sa.column("adapter_type"),
        sa.column("base_url"),
        sa.column("owner"),
        sa.column("query_scope", postgresql.JSONB()),
        sa.column("credentials_ref"),
        sa.column("rate_limit_policy", postgresql.JSONB()),
        sa.column("polling_interval_seconds"),
        sa.column("freshness_slo_seconds"),
        sa.column("checkpoint_strategy"),
        sa.column("checkpoint_state", postgresql.JSONB()),
        sa.column("retry_budget"),
        sa.column("policy_state"),
        sa.column("policy_evidence", postgresql.JSONB()),
        sa.column("policy_reviewed_at"),
        sa.column("participant_reuse_state"),
        sa.column("participant_reuse_evidence", postgresql.JSONB()),
        sa.column("content_storage_policy"),
        sa.column("default_language"),
        sa.column("expected_timezone"),
        sa.column("enabled"),
        sa.column("operating_state"),
        sa.column("last_fetch_at"),
        sa.column("last_success_at"),
        sa.column("last_error_at"),
        sa.column("last_error"),
        sa.column("consecutive_failures"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    rows = []
    for source in sources:
        rows.append(
            {
                "id": str(uuid4()),
                "source_kind": "event",
                "owner": "event-intelligence-service",
                "credentials_ref": None,
                "rate_limit_policy": {"requests_per_minute": 30},
                "polling_interval_seconds": 86400,
                "freshness_slo_seconds": 604800,
                "checkpoint_strategy": "last_success_at",
                "checkpoint_state": {},
                "retry_budget": 3,
                "policy_state": "unknown",
                "policy_evidence": {
                    "note": "Official event discovery seed; terms review required."
                },
                "policy_reviewed_at": None,
                "participant_reuse_state": "unknown",
                "participant_reuse_evidence": {},
                "content_storage_policy": "metadata_excerpt",
                "default_language": "en",
                "expected_timezone": None,
                "enabled": True,
                "operating_state": "enabled",
                "last_fetch_at": None,
                "last_success_at": None,
                "last_error_at": None,
                "last_error": None,
                "consecutive_failures": 0,
                "created_at": now,
                "updated_at": now,
                **source,
            }
        )
    op.bulk_insert(table, rows)
