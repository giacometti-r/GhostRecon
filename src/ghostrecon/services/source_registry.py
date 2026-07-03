from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import ContentStoragePolicy, SourceHealth, SourceHealthStatus
from ghostrecon.models.db import OutboxEvent, RawSourceItem, SourceDefinition
from ghostrecon.services.source_adapters import FetchedSourceItem, create_adapter

TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "msclkid",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    scheme = (parsed.scheme or "https").lower()
    hostname = (parsed.hostname or "").lower()
    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        hostname = f"{hostname}:{port}"
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_param(key)
    ]
    query = urlencode(sorted(query_pairs), doseq=True)
    path = parsed.path or "/"
    return urlunsplit((scheme, hostname, path, query, ""))


def content_hash(content: bytes | str) -> str:
    payload = content if isinstance(content, bytes) else content.encode()
    return hashlib.sha256(payload).hexdigest()


def build_raw_item_idempotency_key(
    source_definition_id: str,
    external_id: str | None,
    canonical_url: str,
    item_content_hash: str,
) -> str:
    identity = external_id or f"{canonical_url}:{item_content_hash}"
    digest = hashlib.sha256(f"{source_definition_id}:{identity}".encode()).hexdigest()
    return f"raw-source-item:{digest}"


def permitted_excerpt(
    content: str,
    storage_policy: str,
    *,
    max_chars: int = 500,
) -> str | None:
    if storage_policy == ContentStoragePolicy.METADATA_ONLY:
        return None
    compact = re.sub(r"\s+", " ", content).strip()
    if not compact:
        return None
    return compact[:max_chars]


def classify_duplicate(
    existing_content_hashes: set[str], item_content_hash: str
) -> tuple[str, str | None]:
    if not existing_content_hashes:
        return "canonical", None
    if item_content_hash in existing_content_hashes:
        return "duplicate", None
    return "quarantined", "canonical_url_content_changed"


def source_health_from_definition(
    source: SourceDefinition, now: datetime | None = None
) -> SourceHealth:
    resolved_now = now or utcnow()
    last_success = _coerce_aware(source.last_success_at)
    freshness_lag_seconds = None
    if last_success is not None:
        freshness_lag_seconds = max(0, int((resolved_now - last_success).total_seconds()))

    status = SourceHealthStatus.UNKNOWN
    if not source.enabled or source.operating_state == "paused":
        status = SourceHealthStatus.DISABLED
    elif source.operating_state == "degraded" or source.consecutive_failures > 0:
        status = SourceHealthStatus.DEGRADED
    elif last_success is None:
        status = SourceHealthStatus.UNKNOWN
    elif freshness_lag_seconds is not None and freshness_lag_seconds > source.freshness_slo_seconds:
        status = SourceHealthStatus.STALE
    else:
        status = SourceHealthStatus.FRESH

    return SourceHealth(
        source_definition_id=source.id,
        name=source.name,
        source_kind=source.source_kind,
        adapter_type=source.adapter_type,
        policy_state=source.policy_state,
        participant_reuse_state=source.participant_reuse_state,
        content_storage_policy=source.content_storage_policy,
        enabled=source.enabled,
        operating_state=source.operating_state,
        freshness_status=status,
        freshness_slo_seconds=source.freshness_slo_seconds,
        freshness_lag_seconds=freshness_lag_seconds,
        checkpoint_state=source.checkpoint_state or {},
        last_fetch_at=source.last_fetch_at,
        last_success_at=source.last_success_at,
        last_error_at=source.last_error_at,
        last_error=source.last_error,
        consecutive_failures=source.consecutive_failures,
    )


async def list_source_health(
    kind: str | None = None, settings: Settings | None = None
) -> list[SourceHealth]:
    async with session_scope(settings) as session:
        repository = SourceRegistryRepository(session)
        return await repository.list_source_health(kind)


async def fetch_source_by_id(
    source_definition_id: str, settings: Settings | None = None
) -> dict[str, object]:
    async with session_scope(settings) as session:
        source = await session.get(SourceDefinition, source_definition_id)
        if source is None:
            raise ValueError(f"unknown source definition {source_definition_id}")

        repository = SourceRegistryRepository(session)
        source.last_fetch_at = utcnow()
        adapter = create_adapter(source.adapter_type)
        try:
            fetched_items = await adapter.fetch(source)
            created_items: list[RawSourceItem] = []
            for fetched in fetched_items:
                raw_item, created = await repository.persist_fetched_item(source, fetched)
                if created:
                    created_items.append(raw_item)
                    repository.enqueue_event(
                        new_event(
                            event_name=EventName.SOURCE_ITEM_INGESTED,
                            aggregate_type="raw_source_item",
                            aggregate_id=raw_item.id,
                            source_service="source-registry",
                            source_definition_id=source.id,
                            source_item_ids=[raw_item.id],
                            payload={
                                "raw_source_item_id": raw_item.id,
                                "canonical_url": raw_item.canonical_url,
                                "content_hash": raw_item.content_hash,
                                "parse_status": raw_item.parse_status,
                                "duplicate_state": raw_item.duplicate_state,
                            },
                            idempotency_key=f"source.item_ingested:{raw_item.id}",
                        )
                    )
            source.last_success_at = utcnow()
            source.last_error_at = None
            source.last_error = None
            source.consecutive_failures = 0
            source.operating_state = "enabled"
            source.checkpoint_state = {
                **(source.checkpoint_state or {}),
                "last_success_at": source.last_success_at.isoformat(),
                "fetched_item_count": len(fetched_items),
                "created_item_count": len(created_items),
            }
            repository.enqueue_event(
                new_event(
                    event_name=EventName.SOURCE_FETCH_SUCCEEDED,
                    aggregate_type="source_definition",
                    aggregate_id=source.id,
                    source_service="source-registry",
                    source_definition_id=source.id,
                    source_item_ids=[item.id for item in created_items],
                    payload={
                        "source_definition_id": source.id,
                        "fetched_item_count": len(fetched_items),
                        "created_item_count": len(created_items),
                    },
                    idempotency_key=f"source.fetch_succeeded:{source.id}:{source.last_success_at.isoformat()}",
                )
            )
            return {
                "status": "succeeded",
                "source_definition_id": source.id,
                "fetched_item_count": len(fetched_items),
                "created_item_count": len(created_items),
            }
        except Exception as exc:  # noqa: BLE001 - failure state is persisted and reported.
            failure_time = utcnow()
            source.last_error_at = failure_time
            source.last_error = str(exc)
            source.consecutive_failures += 1
            source.operating_state = "degraded"
            repository.enqueue_event(
                new_event(
                    event_name=EventName.SOURCE_FETCH_FAILED,
                    aggregate_type="source_definition",
                    aggregate_id=source.id,
                    source_service="source-registry",
                    source_definition_id=source.id,
                    payload={
                        "source_definition_id": source.id,
                        "error": str(exc),
                        "consecutive_failures": source.consecutive_failures,
                    },
                    idempotency_key=f"source.fetch_failed:{source.id}:{failure_time.isoformat()}",
                )
            )
            return {
                "status": "failed",
                "source_definition_id": source.id,
                "error": str(exc),
            }


class SourceRegistryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_source_health(self, kind: str | None = None) -> list[SourceHealth]:
        stmt = select(SourceDefinition).order_by(SourceDefinition.name)
        if kind:
            stmt = stmt.where(SourceDefinition.source_kind == kind)
        result = await self.session.execute(stmt)
        return [source_health_from_definition(source) for source in result.scalars()]

    async def persist_fetched_item(
        self, source: SourceDefinition, fetched: FetchedSourceItem
    ) -> tuple[RawSourceItem, bool]:
        canonical_url = normalize_url(fetched.url)
        item_hash = content_hash(fetched.content)
        idempotency_key = build_raw_item_idempotency_key(
            source.id, fetched.external_id, canonical_url, item_hash
        )

        existing = await self.session.scalar(
            select(RawSourceItem).where(RawSourceItem.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing, False

        hash_result = await self.session.execute(
            select(RawSourceItem.content_hash).where(
                RawSourceItem.source_definition_id == source.id,
                RawSourceItem.canonical_url == canonical_url,
            )
        )
        duplicate_state, quarantine_reason = classify_duplicate(
            set(hash_result.scalars()), item_hash
        )
        parse_status = "quarantined" if duplicate_state == "quarantined" else "pending"
        raw_item = RawSourceItem(
            source_definition_id=source.id,
            external_id=fetched.external_id,
            original_url=fetched.url,
            canonical_url=canonical_url,
            content_hash=item_hash,
            retrieved_at=utcnow(),
            published_at=fetched.published_at,
            original_language=fetched.original_language or source.default_language,
            source_timezone=fetched.source_timezone or source.expected_timezone,
            raw_metadata=_metadata_without_body(fetched.metadata),
            permitted_excerpt=permitted_excerpt(fetched.content, source.content_storage_policy),
            parse_status=parse_status,
            duplicate_state=duplicate_state,
            quarantine_reason=quarantine_reason,
            idempotency_key=idempotency_key,
        )
        self.session.add(raw_item)
        await self.session.flush()
        return raw_item, True

    def enqueue_event(self, event: Any) -> OutboxEvent:
        payload = event.model_dump(mode="json")
        outbox_event = OutboxEvent(
            event_name=payload["event_name"],
            aggregate_type=payload["aggregate_type"],
            aggregate_id=payload["aggregate_id"],
            idempotency_key=payload["idempotency_key"],
            payload=payload,
        )
        self.session.add(outbox_event)
        return outbox_event


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    return lowered.startswith("utm_") or lowered in TRACKING_QUERY_PARAMS


def _coerce_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _metadata_without_body(metadata: dict[str, object]) -> dict[str, object]:
    blocked = {"body", "content", "html", "text"}
    return {key: value for key, value in metadata.items() if key.lower() not in blocked}
