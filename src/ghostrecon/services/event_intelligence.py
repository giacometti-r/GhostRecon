from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    EventParticipantCreate,
    EventUpdateRequest,
    ManualEventCreate,
    normalize_event_format_value,
)
from ghostrecon.models.db import (
    AuditEvent,
    CyberEvent,
    EventParticipant,
    OutboxEvent,
    RawSourceItem,
    SourceDefinition,
)
from ghostrecon.services.geocoding import (
    Geocoder,
    GeocodeRequest,
    GeocodeResult,
    geocoder_for_settings,
)
from ghostrecon.services.source_registry import fetch_source_by_id, normalize_url

EVENT_SERVICE_NAME = "event-intelligence-service"
_ALLOWED_REUSE = "allowed"


@dataclass(frozen=True)
class NormalizedTime:
    original_value: str | None
    source_timezone: str | None
    iana_timezone: str | None
    value_utc: datetime | None
    status: str


@dataclass(frozen=True)
class EventCandidate:
    name: str
    event_series_key: str
    external_id: str | None = None
    canonical_url: str | None = None
    original_start: str | None = None
    original_end: str | None = None
    source_timezone: str | None = None
    iana_timezone: str | None = None
    timezone_status: str = "missing"
    starts_at_utc: datetime | None = None
    ends_at_utc: datetime | None = None
    event_format: str = "unknown"
    venue_name: str | None = None
    street_address: str | None = None
    city: str | None = None
    region: str | None = None
    postcode: str | None = None
    country: str | None = None
    virtual_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    topics: list[object] = field(default_factory=list)
    organizers: list[object] = field(default_factory=list)
    confidence: int = 50
    canonical_state: str = "canonical"


@dataclass(frozen=True)
class ParticipantCandidate:
    published_name: str
    source_participant_id: str | None = None
    organization: str | None = None
    published_role: str | None = None
    participant_type: str = "speaker"
    profile_url: str | None = None
    resolution_confidence: int = 70


def normalize_event_time(value: str | None, timezone_hint: str | None) -> NormalizedTime:
    if not value:
        return NormalizedTime(value, timezone_hint, None, None, "missing")

    parsed = _parse_datetime(value)
    if parsed is None:
        return NormalizedTime(value, timezone_hint, None, None, "ambiguous")

    if parsed.tzinfo is not None:
        return NormalizedTime(
            value,
            timezone_hint,
            _zone_key(parsed.tzinfo) or timezone_hint,
            parsed.astimezone(UTC),
            "resolved",
        )

    if not timezone_hint:
        return NormalizedTime(value, timezone_hint, None, None, "missing")

    try:
        zone = ZoneInfo(timezone_hint)
    except ZoneInfoNotFoundError:
        return NormalizedTime(value, timezone_hint, None, None, "ambiguous")

    if _is_ambiguous_local_time(parsed, zone):
        return NormalizedTime(value, timezone_hint, timezone_hint, None, "ambiguous")

    return NormalizedTime(
        value,
        timezone_hint,
        timezone_hint,
        parsed.replace(tzinfo=zone).astimezone(UTC),
        "resolved",
    )


def build_event_dedupe_key(candidate: EventCandidate) -> str:
    if candidate.external_id:
        identity = f"external:{candidate.event_series_key}:{candidate.external_id}"
    else:
        starts = (
            candidate.starts_at_utc.date().isoformat() if candidate.starts_at_utc else "unknown"
        )
        location = "|".join(
            part or ""
            for part in (
                candidate.country,
                candidate.region,
                candidate.city,
                candidate.event_format,
            )
        )
        identity = f"event:{candidate.event_series_key}:{_slug(candidate.name)}:{starts}:{location}"
    return f"cyber-event:{hashlib.sha256(identity.encode()).hexdigest()}"


def build_participant_dedupe_key(event_id: str, candidate: ParticipantCandidate) -> str:
    if candidate.source_participant_id:
        identity = f"external:{event_id}:{candidate.source_participant_id}"
    elif candidate.profile_url:
        identity = f"profile:{event_id}:{normalize_url(candidate.profile_url)}"
    else:
        identity = "|".join(
            [
                event_id,
                _slug(candidate.published_name),
                _slug(candidate.organization or ""),
                _slug(candidate.published_role or ""),
            ]
        )
    return f"event-participant:{hashlib.sha256(identity.encode()).hexdigest()}"


def participant_eligibility(reuse_state: str) -> tuple[bool, bool]:
    allowed = reuse_state == _ALLOWED_REUSE
    return allowed, allowed


def candidates_from_raw_item(
    source: SourceDefinition, raw_item: RawSourceItem
) -> list[EventCandidate]:
    metadata = raw_item.raw_metadata or {}
    series = str((source.query_scope or {}).get("event_series_key") or _slug(source.name))
    timezone_hint = raw_item.source_timezone or source.expected_timezone

    if isinstance(metadata.get("schema_org_event"), dict):
        return [
            _candidate_from_schema_org(
                metadata["schema_org_event"], source, raw_item, series, timezone_hint
            )
        ]
    if isinstance(metadata.get("ics_event"), dict):
        return [_candidate_from_ics(metadata["ics_event"], source, raw_item, series, timezone_hint)]
    if metadata.get("feed_title"):
        return [_candidate_from_feed(metadata, source, raw_item, series, timezone_hint)]
    return [_candidate_from_page(metadata, source, raw_item, series, timezone_hint)]


def participants_from_raw_item(
    source: SourceDefinition, raw_item: RawSourceItem
) -> list[ParticipantCandidate]:
    metadata = raw_item.raw_metadata or {}
    schema_event = metadata.get("schema_org_event")
    if not isinstance(schema_event, dict):
        return []

    participants: list[ParticipantCandidate] = []
    for field_name, participant_type in (
        ("performer", "speaker"),
        ("speaker", "speaker"),
        ("organizer", "organizer"),
        ("sponsor", "sponsor"),
        ("attendee", "attendee"),
    ):
        for item in _as_list(schema_event.get(field_name)):
            parsed = _participant_from_schema_node(item, participant_type)
            if parsed is not None:
                participants.append(parsed)
    return participants


async def fetch_event_source(
    source_definition_id: str, settings: Settings | None = None
) -> dict[str, object]:
    fetch_result = await fetch_source_by_id(source_definition_id, settings)
    parse_result = await parse_pending_event_items(source_definition_id, settings)
    return {"fetch": fetch_result, "parse": parse_result}


async def parse_pending_event_items(
    source_definition_id: str | None = None, settings: Settings | None = None
) -> dict[str, object]:
    async with session_scope(settings) as session:
        repository = EventIntelligenceRepository(session)
        return await repository.parse_pending_items(source_definition_id)


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


async def create_event_participant(
    event_id: str,
    payload: EventParticipantCreate,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> EventParticipant | None:
    async with session_scope(settings) as session:
        event = await session.get(CyberEvent, event_id)
        if event is None:
            return None
        dedupe_key = f"manual-participant:{event_id}:{idempotency_key}"
        existing = await session.scalar(
            select(EventParticipant).where(EventParticipant.dedupe_key == dedupe_key)
        )
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        participant = EventParticipant(
            cyber_event_id=event_id,
            source_definition_id=event.source_definition_id,
            source_item_id=None,
            source_participant_id=None,
            published_name=payload.published_name,
            organization=payload.organization,
            published_role=payload.published_role,
            participant_type=payload.participant_type.value,
            profile_url=normalize_url(payload.profile_url) if payload.profile_url else None,
            reuse_state=payload.reuse_state.value,
            reuse_evidence={"basis": "manual dashboard entry", "actor": actor},
            contact_extraction_allowed=payload.contact_extraction_allowed,
            crm_export_allowed=payload.crm_export_allowed,
            resolution_confidence=payload.resolution_confidence,
            dedupe_key=dedupe_key,
            created_at=now,
            updated_at=now,
        )
        session.add(participant)
        await session.flush()
        session.add(
            AuditEvent(
                actor=actor,
                action="event_participant.manual_created",
                entity_type="event_participant",
                entity_id=participant.id,
                idempotency_key=idempotency_key,
                payload={"cyber_event_id": event_id},
            )
        )
        return participant


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


async def _geocode_event_payload(
    payload: ManualEventCreate,
    settings: Settings,
    geocoder: Geocoder | None,
) -> GeocodeResult:
    if payload.event_format.value != "in-person":
        return GeocodeResult(None, None, "not_required")
    resolver = geocoder or geocoder_for_settings(settings)
    return await resolver.geocode(
        GeocodeRequest(
            street_address=payload.street_address,
            city=payload.city,
            postcode=payload.postcode,
            country=payload.country,
        )
    )


async def _apply_event_geocode(
    event: CyberEvent,
    settings: Settings,
    geocoder: Geocoder | None,
) -> None:
    if event.event_format != "in-person":
        event.latitude = None
        event.longitude = None
        event.geocode_status = "not_required"
        event.geocode_provider = None
        event.geocode_display_name = None
        event.geocoded_at = None
        return
    if not (event.street_address and event.city and event.postcode and event.country):
        event.geocode_status = "insufficient_address"
        event.latitude = None
        event.longitude = None
        event.geocode_provider = None
        event.geocode_display_name = None
        event.geocoded_at = None
        return
    resolver = geocoder or geocoder_for_settings(settings)
    result = await resolver.geocode(
        GeocodeRequest(
            street_address=event.street_address,
            city=event.city,
            postcode=event.postcode,
            country=event.country,
        )
    )
    event.latitude = result.latitude
    event.longitude = result.longitude
    event.geocode_status = result.status
    event.geocode_provider = result.provider
    event.geocode_display_name = result.display_name
    event.geocoded_at = result.geocoded_at


async def list_participants(
    *,
    event_id: str | None = None,
    reuse_state: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> list[EventParticipant]:
    async with session_scope(settings) as session:
        repository = EventIntelligenceRepository(session)
        return await repository.list_participants(
            event_id=event_id,
            reuse_state=reuse_state,
            limit=limit,
        )


class EventIntelligenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def parse_pending_items(
        self, source_definition_id: str | None = None
    ) -> dict[str, object]:
        stmt = (
            select(RawSourceItem, SourceDefinition)
            .join(SourceDefinition, RawSourceItem.source_definition_id == SourceDefinition.id)
            .where(SourceDefinition.source_kind == "event")
            .where(RawSourceItem.parse_status == "pending")
            .where(RawSourceItem.duplicate_state == "canonical")
            .order_by(RawSourceItem.retrieved_at)
        )
        if source_definition_id:
            stmt = stmt.where(SourceDefinition.id == source_definition_id)
        result = await self.session.execute(stmt)

        parsed_items = 0
        event_count = 0
        participant_count = 0
        failed_items = 0
        for raw_item, source in result.all():
            try:
                events = candidates_from_raw_item(source, raw_item)
                for candidate in events:
                    event, event_created = await self.upsert_event(source, raw_item, candidate)
                    event_count += int(event_created)
                    for participant_candidate in participants_from_raw_item(source, raw_item):
                        _, participant_created = await self.upsert_participant(
                            source, raw_item, event, participant_candidate
                        )
                        participant_count += int(participant_created)
                raw_item.parse_status = "parsed"
                parsed_items += 1
            except Exception as exc:  # noqa: BLE001 - parse failure is persisted on the raw item.
                raw_item.parse_status = "failed"
                raw_item.quarantine_reason = str(exc)
                failed_items += 1
        return {
            "parsed_items": parsed_items,
            "failed_items": failed_items,
            "events_discovered": event_count,
            "participants_discovered": participant_count,
        }

    async def upsert_event(
        self, source: SourceDefinition, raw_item: RawSourceItem, candidate: EventCandidate
    ) -> tuple[CyberEvent, bool]:
        dedupe_key = build_event_dedupe_key(candidate)
        existing = await self.session.scalar(
            select(CyberEvent).where(CyberEvent.dedupe_key == dedupe_key)
        )
        if existing is not None:
            if raw_item.id not in (existing.source_item_ids or []):
                existing.source_item_ids = [*(existing.source_item_ids or []), raw_item.id]
            return existing, False

        event = CyberEvent(
            name=candidate.name,
            event_series_key=candidate.event_series_key,
            external_id=candidate.external_id,
            canonical_url=candidate.canonical_url,
            original_start=candidate.original_start,
            original_end=candidate.original_end,
            source_timezone=candidate.source_timezone,
            iana_timezone=candidate.iana_timezone,
            timezone_status=candidate.timezone_status,
            starts_at_utc=candidate.starts_at_utc,
            ends_at_utc=candidate.ends_at_utc,
            event_format=candidate.event_format,
            venue_name=candidate.venue_name,
            street_address=candidate.street_address,
            city=candidate.city,
            region=candidate.region,
            postcode=candidate.postcode,
            country=candidate.country,
            virtual_url=candidate.virtual_url,
            latitude=candidate.latitude,
            longitude=candidate.longitude,
            geocode_status="resolved"
            if candidate.latitude is not None and candidate.longitude is not None
            else "not_required",
            geocode_provider="source"
            if candidate.latitude is not None and candidate.longitude is not None
            else None,
            geocode_display_name=None,
            geocoded_at=None,
            topics=candidate.topics,
            organizers=candidate.organizers,
            confidence=candidate.confidence,
            canonical_state=candidate.canonical_state,
            dedupe_key=dedupe_key,
            source_definition_id=source.id,
            source_item_ids=[raw_item.id],
            version=1,
        )
        self.session.add(event)
        await self.session.flush()
        self._enqueue_event(
            new_event(
                event_name=EventName.CYBER_EVENT_DISCOVERED,
                aggregate_type="cyber_event",
                aggregate_id=event.id,
                source_service=EVENT_SERVICE_NAME,
                source_definition_id=source.id,
                source_item_ids=[raw_item.id],
                payload={
                    "cyber_event_id": event.id,
                    "event_series_key": event.event_series_key,
                    "starts_at_utc": event.starts_at_utc.isoformat()
                    if event.starts_at_utc
                    else None,
                    "iana_timezone": event.iana_timezone,
                    "country": event.country,
                    "dedupe_outcome": "created",
                },
                idempotency_key=f"cyber_event.discovered:{event.id}",
            )
        )
        return event, True

    async def upsert_participant(
        self,
        source: SourceDefinition,
        raw_item: RawSourceItem,
        event: CyberEvent,
        candidate: ParticipantCandidate,
    ) -> tuple[EventParticipant, bool]:
        dedupe_key = build_participant_dedupe_key(event.id, candidate)
        existing = await self.session.scalar(
            select(EventParticipant).where(EventParticipant.dedupe_key == dedupe_key)
        )
        if existing is not None:
            return existing, False

        contact_allowed, export_allowed = participant_eligibility(source.participant_reuse_state)
        participant = EventParticipant(
            cyber_event_id=event.id,
            source_definition_id=source.id,
            source_item_id=raw_item.id,
            source_participant_id=candidate.source_participant_id,
            published_name=candidate.published_name,
            organization=candidate.organization,
            published_role=candidate.published_role,
            participant_type=candidate.participant_type,
            profile_url=candidate.profile_url,
            reuse_state=source.participant_reuse_state,
            reuse_evidence=source.participant_reuse_evidence or {},
            contact_extraction_allowed=contact_allowed,
            crm_export_allowed=export_allowed,
            resolution_confidence=candidate.resolution_confidence,
            dedupe_key=dedupe_key,
        )
        self.session.add(participant)
        await self.session.flush()
        self._enqueue_event(
            new_event(
                event_name=EventName.EVENT_PARTICIPANT_DISCOVERED,
                aggregate_type="event_participant",
                aggregate_id=participant.id,
                source_service=EVENT_SERVICE_NAME,
                source_definition_id=source.id,
                source_item_ids=[raw_item.id],
                payload={
                    "event_participant_id": participant.id,
                    "cyber_event_id": event.id,
                    "published_role": participant.published_role,
                    "participant_type": participant.participant_type,
                    "reuse_state": participant.reuse_state,
                    "contact_extraction_allowed": participant.contact_extraction_allowed,
                    "crm_export_allowed": participant.crm_export_allowed,
                },
                idempotency_key=f"event_participant.discovered:{participant.id}",
            )
        )
        return participant, True

    async def list_events(
        self,
        *,
        series: str | None,
        source: str | None,
        country: str | None,
        event_format: str | None,
        limit: int,
    ) -> list[CyberEvent]:
        stmt = select(CyberEvent).order_by(CyberEvent.starts_at_utc, CyberEvent.name).limit(limit)
        if series:
            stmt = stmt.where(CyberEvent.event_series_key == series)
        if source:
            stmt = stmt.where(CyberEvent.source_definition_id == source)
        if country:
            stmt = stmt.where(CyberEvent.country == country.upper())
        if event_format:
            stmt = stmt.where(CyberEvent.event_format == event_format)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def list_participants(
        self, *, event_id: str | None, reuse_state: str | None, limit: int
    ) -> list[EventParticipant]:
        stmt = select(EventParticipant).order_by(EventParticipant.published_name).limit(limit)
        if event_id:
            stmt = stmt.where(EventParticipant.cyber_event_id == event_id)
        if reuse_state:
            stmt = stmt.where(EventParticipant.reuse_state == reuse_state)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    def _enqueue_event(self, event: Any) -> OutboxEvent:
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


def event_to_api(event: CyberEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "name": event.name,
        "event_series_key": event.event_series_key,
        "external_id": event.external_id,
        "canonical_url": event.canonical_url,
        "original_start": event.original_start,
        "original_end": event.original_end,
        "source_timezone": event.source_timezone,
        "iana_timezone": event.iana_timezone,
        "timezone_status": event.timezone_status,
        "starts_at_utc": event.starts_at_utc,
        "ends_at_utc": event.ends_at_utc,
        "event_format": event.event_format,
        "venue_name": event.venue_name,
        "street_address": event.street_address,
        "city": event.city,
        "region": event.region,
        "postcode": event.postcode,
        "country": event.country,
        "virtual_url": event.virtual_url,
        "latitude": event.latitude,
        "longitude": event.longitude,
        "geocode_status": event.geocode_status,
        "geocode_provider": event.geocode_provider,
        "geocode_display_name": event.geocode_display_name,
        "geocoded_at": event.geocoded_at,
        "topics": event.topics or [],
        "organizers": event.organizers or [],
        "confidence": event.confidence,
        "canonical_state": event.canonical_state,
        "source_definition_id": event.source_definition_id,
        "source_item_ids": event.source_item_ids or [],
        "version": getattr(event, "version", 1),
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }


def participant_to_api(participant: EventParticipant) -> dict[str, object]:
    return {
        "id": participant.id,
        "cyber_event_id": participant.cyber_event_id,
        "source_definition_id": participant.source_definition_id,
        "source_item_id": participant.source_item_id,
        "source_participant_id": participant.source_participant_id,
        "published_name": participant.published_name,
        "organization": participant.organization,
        "published_role": participant.published_role,
        "participant_type": participant.participant_type,
        "profile_url": participant.profile_url,
        "reuse_state": participant.reuse_state,
        "reuse_evidence": participant.reuse_evidence or {},
        "contact_extraction_allowed": participant.contact_extraction_allowed,
        "crm_export_allowed": participant.crm_export_allowed,
        "resolution_confidence": participant.resolution_confidence,
        "created_at": participant.created_at,
        "updated_at": participant.updated_at,
    }


def _candidate_from_schema_org(
    event: dict[str, object],
    source: SourceDefinition,
    raw_item: RawSourceItem,
    series: str,
    timezone_hint: str | None,
) -> EventCandidate:
    start = _string(event.get("startDate"))
    end = _string(event.get("endDate"))
    start_time = normalize_event_time(start, timezone_hint)
    end_time = normalize_event_time(end, timezone_hint) if end else None
    location = event.get("location") if isinstance(event.get("location"), dict) else {}
    address = location.get("address") if isinstance(location.get("address"), dict) else {}
    geo = location.get("geo") if isinstance(location.get("geo"), dict) else {}
    attendance_mode = _string(event.get("eventAttendanceMode"))
    return EventCandidate(
        name=_string(event.get("name")) or raw_item.permitted_excerpt or source.name,
        event_series_key=series,
        external_id=_string(event.get("@id")) or raw_item.external_id,
        canonical_url=normalize_url(_string(event.get("url")) or raw_item.canonical_url),
        original_start=start,
        original_end=end,
        source_timezone=timezone_hint,
        iana_timezone=start_time.iana_timezone,
        timezone_status=start_time.status,
        starts_at_utc=start_time.value_utc,
        ends_at_utc=end_time.value_utc if end_time else None,
        event_format=_format_from_schema(attendance_mode),
        venue_name=_string(location.get("name")),
        street_address=_string(address.get("streetAddress")),
        city=_string(address.get("addressLocality")),
        region=_string(address.get("addressRegion")),
        postcode=_string(address.get("postalCode")),
        country=_country_code(address.get("addressCountry")),
        virtual_url=_string(event.get("url"))
        if attendance_mode and "online" in attendance_mode.lower()
        else None,
        latitude=_float(geo.get("latitude")),
        longitude=_float(geo.get("longitude")),
        topics=_keywords(event.get("keywords")),
        organizers=[_compact_org(item) for item in _as_list(event.get("organizer"))],
        confidence=85 if start_time.status == "resolved" else 65,
    )


def _candidate_from_ics(
    event: dict[str, object],
    source: SourceDefinition,
    raw_item: RawSourceItem,
    series: str,
    timezone_hint: str | None,
) -> EventCandidate:
    start = _string(event.get("DTSTART"))
    end = _string(event.get("DTEND"))
    start_time = normalize_event_time(_ics_datetime(start), timezone_hint)
    end_time = normalize_event_time(_ics_datetime(end), timezone_hint) if end else None
    location = _string(event.get("LOCATION"))
    return EventCandidate(
        name=_string(event.get("SUMMARY")) or source.name,
        event_series_key=series,
        external_id=_string(event.get("UID")) or raw_item.external_id,
        canonical_url=normalize_url(_string(event.get("URL")) or raw_item.canonical_url),
        original_start=start,
        original_end=end,
        source_timezone=timezone_hint,
        iana_timezone=start_time.iana_timezone,
        timezone_status=start_time.status,
        starts_at_utc=start_time.value_utc,
        ends_at_utc=end_time.value_utc if end_time else None,
        event_format="online" if location and location.lower().startswith("http") else "in-person",
        venue_name=None if location and location.lower().startswith("http") else location,
        virtual_url=location if location and location.lower().startswith("http") else None,
        confidence=80 if start_time.status == "resolved" else 60,
    )


def _candidate_from_feed(
    metadata: dict[str, object],
    source: SourceDefinition,
    raw_item: RawSourceItem,
    series: str,
    timezone_hint: str | None,
) -> EventCandidate:
    start_time = (
        normalize_event_time(raw_item.published_at.isoformat(), timezone_hint)
        if raw_item.published_at
        else None
    )
    return EventCandidate(
        name=_string(metadata.get("feed_title")) or source.name,
        event_series_key=series,
        external_id=raw_item.external_id,
        canonical_url=raw_item.canonical_url,
        original_start=raw_item.published_at.isoformat() if raw_item.published_at else None,
        source_timezone=timezone_hint,
        iana_timezone=start_time.iana_timezone if start_time else None,
        timezone_status=start_time.status if start_time else "missing",
        starts_at_utc=start_time.value_utc if start_time else None,
        event_format="unknown",
        confidence=55,
    )


def _candidate_from_page(
    metadata: dict[str, object],
    source: SourceDefinition,
    raw_item: RawSourceItem,
    series: str,
    timezone_hint: str | None,
) -> EventCandidate:
    title = _string(metadata.get("title")) or raw_item.permitted_excerpt or source.name
    return EventCandidate(
        name=title,
        event_series_key=series,
        external_id=raw_item.external_id,
        canonical_url=raw_item.canonical_url,
        source_timezone=timezone_hint,
        timezone_status="missing",
        event_format="unknown",
        confidence=40,
    )


def _participant_from_schema_node(
    item: object, participant_type: str
) -> ParticipantCandidate | None:
    if isinstance(item, str):
        name = item.strip()
        return (
            ParticipantCandidate(published_name=name, participant_type=participant_type)
            if name
            else None
        )
    if not isinstance(item, dict):
        return None
    name = _string(item.get("name"))
    if not name:
        return None
    affiliation = item.get("affiliation")
    org = (
        _string(affiliation.get("name"))
        if isinstance(affiliation, dict)
        else _string(item.get("worksFor"))
    )
    return ParticipantCandidate(
        published_name=name,
        source_participant_id=_string(item.get("@id")),
        organization=org,
        published_role=_string(item.get("jobTitle")) or participant_type,
        participant_type=participant_type,
        profile_url=_string(item.get("url")) or _string(item.get("sameAs")),
        resolution_confidence=80,
    )


def _parse_datetime(value: str) -> datetime | None:
    compact = value.strip()
    if not compact:
        return None
    if re.fullmatch(r"\d{8}", compact):
        parsed_date = datetime.strptime(compact, "%Y%m%d").date()
        return datetime.combine(parsed_date, time.min)
    if re.fullmatch(r"\d{8}T\d{6}Z", compact):
        return datetime.strptime(compact, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    if re.fullmatch(r"\d{8}T\d{6}", compact):
        return datetime.strptime(compact, "%Y%m%dT%H%M%S")
    try:
        return datetime.fromisoformat(compact.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(compact), time.min)
        except ValueError:
            return None


def _ics_datetime(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip()


def _is_ambiguous_local_time(value: datetime, zone: ZoneInfo) -> bool:
    first = value.replace(tzinfo=zone, fold=0).utcoffset()
    second = value.replace(tzinfo=zone, fold=1).utcoffset()
    return first != second


def _format_from_schema(attendance_mode: str | None) -> str:
    if not attendance_mode:
        return "unknown"
    lowered = attendance_mode.lower()
    if "mixed" in lowered:
        return "hybrid"
    if "online" in lowered:
        return "online"
    if "offline" in lowered:
        return "in-person"
    return "unknown"


def _as_list(value: object) -> list[object]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _keywords(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _compact_org(item: object) -> object:
    if isinstance(item, dict):
        return {key: item[key] for key in ("name", "url", "@id") if key in item}
    return item


def _country_code(value: object) -> str | None:
    text = _string(value)
    if not text:
        return None
    return text.upper() if len(text) == 2 else text[:2].upper()


def _string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return _string(value[0]) if value else None
    text = str(value).strip()
    return text or None


def _float(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown"


def _zone_key(value: object) -> str | None:
    return getattr(value, "key", None)
