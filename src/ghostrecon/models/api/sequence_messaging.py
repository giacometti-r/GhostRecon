from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)

from .sequence_definitions import InboundEmailEventType


class CrmProspectOut(BaseModel):
    provider: str = "attio"
    provider_record_id: str
    provider_object: str = "people"
    display_name: str
    email: EmailStr | None = None
    title: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    source_payload: dict[str, object] = {}


class CrmProspectList(BaseModel):
    prospects: list[CrmProspectOut]
    provider: str = "attio"


class SequenceCrmProspectImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_record_id: str
    sequence_id: str
    outreach_approved: bool
    approval_reason: str = Field(min_length=1, max_length=500)
    start_at: datetime | None = None
    policy_snapshot: dict[str, object] = {}


class SequenceEmailAlertCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_email: EmailStr
    subject: str = Field(min_length=1, max_length=512)
    body: str = Field(min_length=1)
    send_at: datetime | None = None


class SequenceEmailAlertOut(BaseModel):
    id: str
    enrollment_id: str
    recipient_email: EmailStr
    subject: str
    body: str
    send_at: datetime
    status: str
    actor: str
    provider_message_id: str | None = None
    last_error: str | None = None
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class InboundEmailEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: InboundEmailEventType
    from_email: EmailStr | None = None
    to_email: EmailStr | None = None
    message_id: str | None = None
    provider_message_id: str | None = None
    provider_payload: dict[str, object] = {}
    occurred_at: datetime | None = None


class UnsubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    domain: str | None = None
    channel: str = "email"
    reason: str = "unsubscribe"
    provider_payload: dict[str, object] = {}


class InboundEmailEventOut(BaseModel):
    id: str
    enrollment_id: str | None = None
    outbound_email_id: str | None = None
    event_type: InboundEmailEventType
    from_email: EmailStr | None = None
    to_email: EmailStr | None = None
    message_id: str | None = None
    provider_payload: dict[str, object] = {}
    occurred_at: datetime
    created_at: datetime
