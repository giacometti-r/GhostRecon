from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)

from .sequence_definitions import OutboundEmailStatus, SequenceEnrollmentStatus


class SequenceEnrollmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_id: str
    crm_target_id: str
    contact_id: str | None = None
    account_id: str | None = None
    start_at: datetime | None = None
    outreach_approved: bool
    approval_reason: str = Field(min_length=1, max_length=500)
    policy_snapshot: dict[str, object] = {}


class SequenceEnrollmentActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class OutboundEmailOut(BaseModel):
    id: str
    enrollment_id: str
    sequence_step_id: str
    contact_id: str
    channel: str
    to_email: EmailStr
    from_email: EmailStr
    subject: str
    status: OutboundEmailStatus
    provider_message_id: str | None = None
    attempt_count: int
    last_error: str | None = None
    retry_after_seconds: int | None = None
    scheduled_at: datetime
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SequenceEnrollmentOut(BaseModel):
    id: str
    sequence_id: str
    crm_target_id: str
    contact_id: str
    account_id: str | None = None
    sequence_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    account_name: str | None = None
    account_domain: str | None = None
    crm_target_summary: str | None = None
    status: SequenceEnrollmentStatus
    approval_actor: str
    approval_reason: str
    current_step_order: int
    definition_version: int = 1
    next_step_at: datetime | None = None
    pause_reason: str | None = None
    policy_snapshot: dict[str, object] = {}
    version: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    outbound_emails: list[OutboundEmailOut] = []


class SequenceEnrollmentList(BaseModel):
    enrollments: list[SequenceEnrollmentOut]
