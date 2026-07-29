import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.db import (
    Account,
    Contact,
    ContactEnrichmentCandidate,
    CrmExportBatch,
    CrmExportItem,
    CrmTarget,
    CyberEvent,
    EmailCandidateRecord,
    EntityResolutionCase,
    EventParticipant,
    MeetingFollowUpTask,
    MeetingHandoff,
    MeetingPrepPacket,
    ReviewCandidate,
    SecurityIncident,
    Sequence,
    SequenceEnrollment,
    SequenceStep,
    SequenceStepActivity,
    SourceDefinition,
    WatchTarget,
    WatchTargetMonitoringRun,
)

from .ids import DEMO_SEED_IDS


def _selection_hash(target_ids: list[str]) -> str:
    payload = json.dumps(sorted(target_ids), separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


async def _get_or_create(session: AsyncSession, model: type[Any], record_id: str) -> Any:
    record = await session.get(model, record_id)
    if record is not None:
        return record
    record = model(id=record_id)
    session.add(record)
    return record


async def _seeded_counts(settings: Settings) -> dict[str, int]:
    async with session_scope(settings) as session:
        counts = {
            "source_definitions": await _count_seeded(session, SourceDefinition),
            "cyber_events": await _count_seeded(session, CyberEvent),
            "event_participants": await _count_seeded(session, EventParticipant),
            "security_incidents": await _count_seeded(session, SecurityIncident),
            "watch_targets": await _count_seeded(session, WatchTarget),
            "watch_target_monitoring_runs": await _count_seeded(session, WatchTargetMonitoringRun),
            "entity_resolution_cases": await _count_seeded(session, EntityResolutionCase),
            "contact_enrichment_candidates": await _count_seeded(
                session, ContactEnrichmentCandidate
            ),
            "email_candidates": await _count_seeded(session, EmailCandidateRecord),
            "review_candidates": await _count_seeded(session, ReviewCandidate),
            "crm_targets": await _count_seeded(session, CrmTarget),
            "crm_export_batches": await _count_seeded(session, CrmExportBatch),
            "crm_export_items": await _count_seeded(session, CrmExportItem),
            "accounts": await _count_seeded(session, Account),
            "contacts": await _count_seeded(session, Contact),
            "sequences": await _count_seeded(session, Sequence),
            "sequence_steps": await _count_seeded(session, SequenceStep),
            "sequence_enrollments": await _count_seeded(session, SequenceEnrollment),
            "sequence_step_activities": await _count_seeded(session, SequenceStepActivity),
            "meeting_handoffs": await _count_seeded(session, MeetingHandoff),
            "meeting_prep_packets": await _count_seeded(session, MeetingPrepPacket),
            "meeting_follow_up_tasks": await _count_seeded(session, MeetingFollowUpTask),
        }
    return counts


async def _count_seeded(session: AsyncSession, model: type[Any]) -> int:
    result = await session.execute(
        select(model).where(model.id.in_(DEMO_SEED_IDS.__dict__.values()))
    )
    return len(list(result.scalars()))
