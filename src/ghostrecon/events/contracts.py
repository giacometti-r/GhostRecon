from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventName(StrEnum):
    ACCOUNT_INGESTED = "account.ingested"
    ACCOUNT_ENRICHED = "account.enriched"
    CONTACT_DISCOVERED = "contact.discovered"
    EMAIL_CANDIDATE_GENERATED = "email.candidate_generated"
    EMAIL_VERIFIED = "email.verified"
    LEAD_SCORED = "lead.scored"
    APPROVAL_REQUESTED = "approval.requested"
    SEQUENCE_ENROLLED = "sequence.enrolled"
    EMAIL_SENT = "email.sent"
    REPLY_RECEIVED = "reply.received"
    MEETING_BOOKED = "meeting.booked"
    CRM_SYNCED = "crm.synced"
    SOURCE_FETCH_SUCCEEDED = "source.fetch_succeeded"
    SOURCE_FETCH_FAILED = "source.fetch_failed"
    SOURCE_ITEM_INGESTED = "source.item_ingested"
    CYBER_EVENT_DISCOVERED = "cyber_event.discovered"
    EVENT_PARTICIPANT_DISCOVERED = "event_participant.discovered"
    NEWS_ARTICLE_INGESTED = "news_article.ingested"
    SECURITY_INCIDENT_DETECTED = "security_incident.detected"
    SECURITY_INCIDENT_CORROBORATED = "security_incident.corroborated"
    WATCH_TARGET_CREATED = "watch_target.created"
    JOB_FAILED = "job.failed"


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    event_name: EventName
    schema_version: str = "1.0"
    producer: str | None = None
    aggregate_type: str
    aggregate_id: str
    idempotency_key: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID = Field(default_factory=uuid4)
    source_service: str
    source_definition_id: str | None = None
    source_item_ids: list[str] = Field(default_factory=list)
    payload: dict[str, object]


def new_event(
    *,
    event_name: EventName,
    aggregate_type: str,
    aggregate_id: str,
    source_service: str,
    payload: dict[str, object],
    idempotency_key: str | None = None,
    correlation_id: UUID | None = None,
    source_definition_id: str | None = None,
    source_item_ids: list[str] | None = None,
    schema_version: str = "1.0",
) -> EventEnvelope:
    return EventEnvelope(
        event_name=event_name,
        schema_version=schema_version,
        producer=source_service,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        idempotency_key=idempotency_key or f"{event_name}:{aggregate_type}:{aggregate_id}",
        correlation_id=correlation_id or uuid4(),
        source_service=source_service,
        source_definition_id=source_definition_id,
        source_item_ids=source_item_ids or [],
        payload=payload,
    )
