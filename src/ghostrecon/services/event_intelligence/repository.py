from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.db import (
    CyberEvent,
    EventParticipant,
    OutboxEvent,
    RawSourceItem,
    SourceDefinition,
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


from .candidates import (  # noqa: E402  # noqa: E402
    EVENT_SERVICE_NAME,
    EventCandidate,
    ParticipantCandidate,
    build_event_dedupe_key,
    build_participant_dedupe_key,
    candidates_from_raw_item,
    participant_eligibility,
    participants_from_raw_item,
)
