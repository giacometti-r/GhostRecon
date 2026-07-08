"""add incident intelligence runtime

Revision ID: 0004_incident_intelligence
Revises: 0003_event_intelligence
Create Date: 2026-07-03
"""

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_incident_intelligence"
down_revision = "0003_event_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_articles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("publisher", sa.String(length=255)),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("permitted_excerpt", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True)),
        sa.Column("original_language", sa.String(length=16)),
        sa.Column("translated_title", sa.String(length=512)),
        sa.Column("translation_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("syndication_cluster_key", sa.String(length=255), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column(
            "source_definition_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("source_definitions.id", ondelete="SET NULL"),
        ),
        sa.Column("source_item_ids", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dedupe_key", name="uq_news_articles_dedupe_key"),
    )
    op.create_index("ix_news_articles_published", "news_articles", ["published_at"])
    op.create_index("ix_news_articles_source_definition", "news_articles", ["source_definition_id"])
    op.create_index("ix_news_articles_syndication", "news_articles", ["syndication_cluster_key"])

    op.create_table(
        "security_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("affected_companies", postgresql.JSONB(), nullable=False),
        sa.Column("affected_domains", postgresql.JSONB(), nullable=False),
        sa.Column("incident_type", sa.String(length=128)),
        sa.Column("attack_vector", sa.String(length=128)),
        sa.Column("first_observed_at", sa.DateTime(timezone=True)),
        sa.Column("last_observed_at", sa.DateTime(timezone=True)),
        sa.Column("geography", postgresql.JSONB(), nullable=False),
        sa.Column("languages", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("evidence_article_ids", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_source_item_ids", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_families", postgresql.JSONB(), nullable=False),
        sa.Column("corroboration_method", sa.String(length=64), nullable=False),
        sa.Column("analyst_decision_ref", sa.String(length=255)),
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
        sa.UniqueConstraint("dedupe_key", name="uq_security_incidents_dedupe_key"),
    )
    op.create_index("ix_security_incidents_status", "security_incidents", ["status"])
    op.create_index(
        "ix_security_incidents_source_definition",
        "security_incidents",
        ["source_definition_id"],
    )
    op.create_index(
        "ix_security_incidents_canonical_state",
        "security_incidents",
        ["canonical_state"],
    )

    op.create_table(
        "security_incident_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "security_incident_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("security_incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "news_article_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("news_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_item_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("raw_source_items.id", ondelete="SET NULL"),
        ),
        sa.Column("evidence_family_key", sa.String(length=255), nullable=False),
        sa.Column("evidence_role", sa.String(length=64), nullable=False),
        sa.Column("authoritative", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "security_incident_id",
            "news_article_id",
            name="uq_security_incident_evidence_incident_article",
        ),
    )
    op.create_index(
        "ix_security_incident_evidence_incident",
        "security_incident_evidence",
        ["security_incident_id"],
    )
    op.create_index(
        "ix_security_incident_evidence_article",
        "security_incident_evidence",
        ["news_article_id"],
    )

    op.create_table(
        "watch_targets",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("canonical_target_key", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("query_config", postgresql.JSONB(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("owner", sa.String(length=128)),
        sa.Column(
            "origin_incident_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("security_incidents.id", ondelete="SET NULL"),
        ),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "target_type", "canonical_target_key", name="uq_watch_targets_type_key"
        ),
    )
    op.create_index("ix_watch_targets_type_enabled", "watch_targets", ["target_type", "enabled"])
    op.create_index("ix_watch_targets_origin_incident", "watch_targets", ["origin_incident_id"])

    _seed_incident_sources()


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM source_definitions WHERE name IN ("
            "'GDELT cyber incident discovery', "
            "'CISA cybersecurity advisories', "
            "'The Hacker News RSS'"
            ")"
        )
    )
    op.drop_index("ix_watch_targets_origin_incident", table_name="watch_targets")
    op.drop_index("ix_watch_targets_type_enabled", table_name="watch_targets")
    op.drop_table("watch_targets")
    op.drop_index("ix_security_incident_evidence_article", table_name="security_incident_evidence")
    op.drop_index("ix_security_incident_evidence_incident", table_name="security_incident_evidence")
    op.drop_table("security_incident_evidence")
    op.drop_index("ix_security_incidents_canonical_state", table_name="security_incidents")
    op.drop_index("ix_security_incidents_source_definition", table_name="security_incidents")
    op.drop_index("ix_security_incidents_status", table_name="security_incidents")
    op.drop_table("security_incidents")
    op.drop_index("ix_news_articles_syndication", table_name="news_articles")
    op.drop_index("ix_news_articles_source_definition", table_name="news_articles")
    op.drop_index("ix_news_articles_published", table_name="news_articles")
    op.drop_table("news_articles")


def _seed_incident_sources() -> None:
    now = datetime.now(UTC)
    sources = [
        {
            "name": "GDELT cyber incident discovery",
            "adapter_type": "gdelt_doc",
            "base_url": "https://api.gdeltproject.org/api/v2/doc/doc",
            "query_scope": {
                "params": {
                    "query": '(ransomware OR "data breach" OR cyberattack OR "cyber incident")',
                    "mode": "artlist",
                    "format": "json",
                    "maxrecords": 100,
                    "timespan": "1d",
                    "sort": "datedesc",
                }
            },
            "freshness_slo_seconds": 86400,
        },
        {
            "name": "CISA cybersecurity advisories",
            "adapter_type": "rss_atom",
            "base_url": "https://www.cisa.gov/news.xml",
            "query_scope": {"authoritative": True, "topic": "cybersecurity_advisories"},
            "freshness_slo_seconds": 86400,
        },
        {
            "name": "The Hacker News RSS",
            "adapter_type": "rss_atom",
            "base_url": "https://feeds.feedburner.com/TheHackersNews",
            "query_scope": {"trusted_publisher": True, "topic": "cybersecurity_news"},
            "freshness_slo_seconds": 43200,
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
                "source_kind": "incident",
                "owner": "incident-intelligence-service",
                "credentials_ref": None,
                "rate_limit_policy": {"requests_per_minute": 20},
                "polling_interval_seconds": 3600,
                "checkpoint_strategy": "last_success_at",
                "checkpoint_state": {},
                "retry_budget": 3,
                "policy_state": "unknown",
                "policy_evidence": {
                    "note": "Discovery seed; terms review required before expansion."
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
