from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from .governance import SuppressionCheckResult
from .scoring import ScoreResult


class SequenceStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class SequenceChannel(StrEnum):
    EMAIL = "email"
    CALL = "call"
    GOOGLE_MEET = "google_meet"


class SequenceEnrollmentStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELED = "canceled"
    SUPPRESSED = "suppressed"
    FAILED = "failed"


class OutboundEmailStatus(StrEnum):
    PENDING = "pending"
    PENDING_APPROVAL = "pending_approval"
    SENT = "sent"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"
    SKIPPED_POLICY = "skipped_policy"


class SequenceActivityStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    PENDING = "pending"
    APPROVED = "approved"
    COMPLETED = "completed"
    SCHEDULED = "scheduled"
    CANCELED = "canceled"
    FAILED = "failed"


class InboundEmailEventType(StrEnum):
    REPLY = "reply"
    BOUNCE = "bounce"
    UNSUBSCRIBE = "unsubscribe"


class SequenceEligibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact: dict[str, object]
    score: ScoreResult
    suppression: SuppressionCheckResult


class SequenceEligibilityResult(BaseModel):
    eligible: bool
    next_action: str
    requires_approval: bool
    reasons: list[str]


class SequenceStepCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_order: int | None = Field(default=None, ge=1)
    delay_seconds: int = Field(default=0, ge=0)
    subject_template: str | None = Field(default=None, max_length=512)
    body_template: str | None = None
    channel: SequenceChannel = SequenceChannel.EMAIL
    requires_approval: bool | None = None
    step_metadata: dict[str, object] = {}

    @model_validator(mode="after")
    def validate_channel_content(self) -> "SequenceStepCreate":
        if self.channel == SequenceChannel.EMAIL:
            if not self.subject_template or not self.subject_template.strip():
                raise ValueError("email sequence steps require a subject template")
            if not self.body_template or not self.body_template.strip():
                raise ValueError("email sequence steps require a body template")
        return self


class SequenceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    owner_id: str | None = None
    channel: SequenceChannel = SequenceChannel.EMAIL
    rate_limit_policy: dict[str, object] = {}
    steps: list[SequenceStepCreate] = Field(min_length=1, max_length=20)


class SequenceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    owner_id: str | None = None
    channel: SequenceChannel | None = None
    status: SequenceStatus | None = None
    rate_limit_policy: dict[str, object] | None = None
    steps: list[SequenceStepCreate] | None = Field(default=None, max_length=20)
    expected_version: int | None = Field(default=None, ge=1)


class SequenceStepOut(BaseModel):
    id: str
    sequence_id: str
    step_order: int
    channel: SequenceChannel
    delay_seconds: int
    subject_template: str | None = None
    body_template: str | None = None
    requires_approval: bool = False
    step_metadata: dict[str, object] = {}
    definition_version: int = 1
    active: bool
    created_at: datetime
    updated_at: datetime


class SequenceOut(BaseModel):
    id: str
    name: str
    owner_id: str | None = None
    channel: SequenceChannel
    status: SequenceStatus
    rate_limit_policy: dict[str, object] = {}
    definition_version: int = 1
    created_at: datetime
    updated_at: datetime
    steps: list[SequenceStepOut] = []


class SequenceList(BaseModel):
    sequences: list[SequenceOut]
