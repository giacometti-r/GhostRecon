from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    EventUpdateRequest,
    ManualEventCreate,
    normalize_event_format_value,
)
from ghostrecon.models.db import (
    AuditEvent,
    CyberEvent,
    OutboxEvent,
)
from ghostrecon.services.geocoding import (
    Geocoder,
)
from ghostrecon.services.source_registry import normalize_url


async def list_events(
    *,
    series: str | None = None,
    source: str | None = None,
    country: str | None = None,
    event_format: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> list[CyberEvent]:
    normalized_format = normalize_event_format_value(event_format) if event_format else None
    async with session_scope(settings) as session:
        repository = EventIntelligenceRepository(session)
        return await repository.list_events(
            series=series,
            source=source,
            country=country,
            event_format=str(normalized_format) if normalized_format else None,
            limit=limit,
        )


async def get_event(event_id: str, settings: Settings | None = None) -> CyberEvent | None:
    async with session_scope(settings) as session:
        return await session.get(CyberEvent, event_id)


async def create_manual_event(
    payload: ManualEventCreate,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
    geocoder: Geocoder | None = None,
) -> CyberEvent:
    resolved = settings or Settings()
    _validate_manual_event(payload)
    geocode = await _geocode_event_payload(payload, resolved, geocoder)
    async with session_scope(resolved) as session:
        existing = await session.scalar(
            select(CyberEvent).where(CyberEvent.dedupe_key == f"manual-event:{idempotency_key}")
        )
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        event = CyberEvent(
            name=payload.name,
            event_series_key=payload.event_series_key,
            external_id=None,
            canonical_url=normalize_url(payload.canonical_url),
            original_start=payload.original_start,
            original_end=payload.original_end,
            source_timezone=payload.source_timezone,
            iana_timezone=payload.iana_timezone,
            timezone_status="resolved" if payload.starts_at_utc else "missing",
            starts_at_utc=payload.starts_at_utc,
            ends_at_utc=payload.ends_at_utc,
            event_format=payload.event_format.value,
            venue_name=payload.venue_name,
            street_address=payload.street_address,
            city=payload.city,
            region=payload.region,
            postcode=payload.postcode,
            country=payload.country.upper() if payload.country else None,
            virtual_url=normalize_url(payload.virtual_url) if payload.virtual_url else None,
            latitude=geocode.latitude,
            longitude=geocode.longitude,
            geocode_status=geocode.status,
            geocode_provider=geocode.provider,
            geocode_display_name=geocode.display_name,
            geocoded_at=geocode.geocoded_at,
            topics=list(payload.topics),
            organizers=list(payload.organizers),
            confidence=payload.confidence,
            canonical_state="canonical",
            dedupe_key=f"manual-event:{idempotency_key}",
            source_definition_id=None,
            source_item_ids=list(payload.source_item_ids),
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(event)
        await session.flush()
        session.add(
            AuditEvent(
                actor=actor,
                action="cyber_event.manual_created",
                entity_type="cyber_event",
                entity_id=event.id,
                idempotency_key=idempotency_key,
                payload={"source": "manual"},
            )
        )
        session.add(
            OutboxEvent(
                event_name=EventName.CYBER_EVENT_DISCOVERED.value,
                aggregate_type="cyber_event",
                aggregate_id=event.id,
                idempotency_key=f"cyber_event.manual:{event.id}",
                payload=new_event(
                    event_name=EventName.CYBER_EVENT_DISCOVERED,
                    aggregate_type="cyber_event",
                    aggregate_id=event.id,
                    source_service=EVENT_SERVICE_NAME,
                    payload={
                        "cyber_event_id": event.id,
                        "event_series_key": event.event_series_key,
                        "manual": True,
                        "created_by": actor,
                    },
                    idempotency_key=f"cyber_event.manual:{event.id}",
                ).model_dump(mode="json"),
            )
        )
        return event


async def update_event(
    event_id: str,
    payload: EventUpdateRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
    geocoder: Geocoder | None = None,
) -> CyberEvent | None:
    resolved = settings or Settings()
    async with session_scope(resolved) as session:
        event = await session.get(CyberEvent, event_id)
        if event is None:
            return None
        if event.version != payload.version:
            raise ValueError("stale optimistic version")
        fields = payload.model_fields_set - {"version"}
        if "name" in fields and payload.name is not None:
            event.name = payload.name
        if "event_series_key" in fields and payload.event_series_key is not None:
            event.event_series_key = payload.event_series_key
        if "canonical_url" in fields:
            event.canonical_url = (
                normalize_url(payload.canonical_url) if payload.canonical_url else None
            )
        if "original_start" in fields:
            event.original_start = payload.original_start
        if "original_end" in fields:
            event.original_end = payload.original_end
        if "source_timezone" in fields:
            event.source_timezone = payload.source_timezone
        if "iana_timezone" in fields:
            event.iana_timezone = payload.iana_timezone
        if "starts_at_utc" in fields:
            event.starts_at_utc = payload.starts_at_utc
            event.timezone_status = "resolved" if payload.starts_at_utc else event.timezone_status
        if "ends_at_utc" in fields:
            event.ends_at_utc = payload.ends_at_utc
        if "event_format" in fields and payload.event_format is not None:
            event.event_format = payload.event_format.value
        if "venue_name" in fields:
            event.venue_name = payload.venue_name
        if "street_address" in fields:
            event.street_address = payload.street_address
        if "city" in fields:
            event.city = payload.city
        if "region" in fields:
            event.region = payload.region
        if "postcode" in fields:
            event.postcode = payload.postcode
        if "country" in fields:
            event.country = payload.country.upper() if payload.country else None
        if "virtual_url" in fields:
            event.virtual_url = normalize_url(payload.virtual_url) if payload.virtual_url else None
        if "topics" in fields and payload.topics is not None:
            event.topics = list(payload.topics)
        if "organizers" in fields and payload.organizers is not None:
            event.organizers = list(payload.organizers)
        if "source_item_ids" in fields and payload.source_item_ids is not None:
            event.source_item_ids = list(payload.source_item_ids)
        if "confidence" in fields and payload.confidence is not None:
            event.confidence = payload.confidence
        await _apply_event_geocode(event, resolved, geocoder)
        event.version += 1
        event.updated_at = datetime.now(UTC)
        session.add(
            AuditEvent(
                actor=actor,
                action="cyber_event.updated",
                entity_type="cyber_event",
                entity_id=event.id,
                idempotency_key=idempotency_key,
                payload={"updated_fields": sorted(fields)},
            )
        )
        return event


def _validate_manual_event(payload: ManualEventCreate) -> None:
    if payload.event_format.value == "in-person":
        missing = [
            label
            for label, value in (
                ("street_address", payload.street_address),
                ("city", payload.city),
                ("postcode", payload.postcode),
                ("country", payload.country),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"in-person event requires {', '.join(missing)}")


from .candidates import EVENT_SERVICE_NAME  # noqa: E402  # noqa: E402
from .geocoding import _apply_event_geocode, _geocode_event_payload  # noqa: E402
from .repository import EventIntelligenceRepository  # noqa: E402  # noqa: E402
