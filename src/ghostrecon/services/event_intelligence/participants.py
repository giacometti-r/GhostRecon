from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    EventParticipantCreate,
)
from ghostrecon.models.db import (
    AuditEvent,
    CyberEvent,
    EventParticipant,
)
from ghostrecon.services.source_registry import normalize_url


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


from .repository import EventIntelligenceRepository  # noqa: E402  # noqa: E402
