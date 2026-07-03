from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from ghostrecon.models.api import SourceHealthStatus
from ghostrecon.services.source_registry import (
    build_raw_item_idempotency_key,
    classify_duplicate,
    content_hash,
    normalize_url,
    permitted_excerpt,
    source_health_from_definition,
)


def _source(**overrides):
    values = {
        "id": "source-1",
        "name": "Example Source",
        "source_kind": "event",
        "adapter_type": "rss_atom",
        "policy_state": "allowed",
        "participant_reuse_state": "unknown",
        "content_storage_policy": "metadata_excerpt",
        "enabled": True,
        "operating_state": "enabled",
        "freshness_slo_seconds": 3600,
        "checkpoint_state": {"cursor": "abc"},
        "last_fetch_at": None,
        "last_success_at": None,
        "last_error_at": None,
        "last_error": None,
        "consecutive_failures": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_normalize_url_removes_tracking_and_sorts_query() -> None:
    assert (
        normalize_url("HTTPS://Example.COM:443/path?utm_source=x&b=2&a=1&fbclid=bad#section")
        == "https://example.com/path?a=1&b=2"
    )


def test_content_hash_and_idempotency_key_are_stable() -> None:
    digest = content_hash("same content")

    assert digest == content_hash(b"same content")
    assert build_raw_item_idempotency_key("source-1", "external-1", "https://x/", digest) == (
        build_raw_item_idempotency_key("source-1", "external-1", "https://changed/", "other")
    )
    assert build_raw_item_idempotency_key("source-1", None, "https://x/", digest) != (
        build_raw_item_idempotency_key("source-1", None, "https://x/", "other")
    )


def test_permitted_excerpt_respects_storage_policy_and_bounds() -> None:
    body = " ".join(["word"] * 200)

    assert permitted_excerpt(body, "metadata_only") is None
    assert permitted_excerpt(body, "metadata_excerpt", max_chars=32) == body[:32]
    assert permitted_excerpt("  alpha\n beta  ", "licensed_body") == "alpha beta"


def test_duplicate_classification_quarantines_changed_content_for_same_url() -> None:
    assert classify_duplicate(set(), "hash-a") == ("canonical", None)
    assert classify_duplicate({"hash-a"}, "hash-a") == ("duplicate", None)
    assert classify_duplicate({"hash-a"}, "hash-b") == (
        "quarantined",
        "canonical_url_content_changed",
    )


def test_source_health_statuses() -> None:
    now = datetime(2026, 6, 26, tzinfo=UTC)

    assert source_health_from_definition(_source(enabled=False), now).freshness_status == (
        SourceHealthStatus.DISABLED
    )
    assert source_health_from_definition(_source(consecutive_failures=1), now).freshness_status == (
        SourceHealthStatus.DEGRADED
    )
    assert (
        source_health_from_definition(_source(), now).freshness_status == SourceHealthStatus.UNKNOWN
    )
    assert (
        source_health_from_definition(
            _source(last_success_at=now - timedelta(minutes=10)), now
        ).freshness_status
        == SourceHealthStatus.FRESH
    )
    assert (
        source_health_from_definition(
            _source(last_success_at=now - timedelta(hours=2)), now
        ).freshness_status
        == SourceHealthStatus.STALE
    )
