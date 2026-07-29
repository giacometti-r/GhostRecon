from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)

from .reporting import ReportingMetadata


class MeetingStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED_SYNC = "failed_sync"


class MeetingOutcomeStatus(StrEnum):
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"
    DISQUALIFIED = "disqualified"


class MeetingCrmSyncStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"


class MeetingFollowUpTaskStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    CANCELED = "canceled"


class PrepPacketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account: dict[str, object]
    contacts: list[dict[str, object]] = []
    signals: list[dict[str, object]] = []
    meeting_time: datetime | None = None


class PrepPacket(BaseModel):
    account_summary: str
    stakeholder_map: list[str]
    likely_security_priorities: list[str]
    suggested_questions: list[str]
    risks: list[str]


class MeetingAttendee(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    name: str | None = None
    optional: bool = False


class MeetingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crm_target_id: str
    sequence_enrollment_id: str | None = None
    account_id: str | None = None
    contact_id: str | None = None
    subject: str = Field(min_length=1, max_length=512)
    description: str | None = None
    location: str | None = None
    start_at: datetime
    end_at: datetime
    timezone: str = "UTC"
    attendees: list[MeetingAttendee] = []
    policy_snapshot: dict[str, object] = {}
    send_updates: bool | None = None


class MeetingActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class MeetingFollowUpTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=512)
    description: str | None = None
    owner: str | None = None
    due_at: datetime | None = None


class MeetingOutcomeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome_status: MeetingOutcomeStatus = MeetingOutcomeStatus.COMPLETED
    outcome_notes: str | None = None
    next_steps: list[str] = []
    follow_up_tasks: list[MeetingFollowUpTaskCreate] = []


class CalendarAvailabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attendees: list[EmailStr] = Field(min_length=1, max_length=50)
    time_min: datetime
    time_max: datetime
    timezone: str = "UTC"


class CalendarBusySlot(BaseModel):
    start: datetime
    end: datetime


class CalendarAvailabilityResult(BaseModel):
    calendars: dict[str, list[CalendarBusySlot]]
    provider: str = "google"


class MeetingPrepPacketOut(BaseModel):
    id: str
    meeting_id: str
    account_summary: str
    stakeholder_map: list[object] = []
    likely_security_priorities: list[object] = []
    suggested_questions: list[object] = []
    risks: list[object] = []
    source_snapshot: dict[str, object] = {}
    generated_by: str
    created_at: datetime
    updated_at: datetime


class MeetingFollowUpTaskOut(BaseModel):
    id: str
    meeting_id: str
    title: str
    description: str | None = None
    owner: str | None = None
    due_at: datetime | None = None
    status: MeetingFollowUpTaskStatus
    crm_sync_status: MeetingCrmSyncStatus
    provider_task_id: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class MeetingHandoffOut(BaseModel):
    id: str
    crm_target_id: str | None = None
    sequence_enrollment_id: str | None = None
    account_id: str | None = None
    contact_id: str | None = None
    status: MeetingStatus
    subject: str
    description: str | None = None
    location: str | None = None
    start_at: datetime
    end_at: datetime
    timezone: str
    attendees: list[object] = []
    calendar_provider: str
    calendar_id: str | None = None
    provider_event_id: str | None = None
    provider_html_link: str | None = None
    outcome_status: MeetingOutcomeStatus | None = None
    outcome_notes: str | None = None
    next_steps: list[object] = []
    crm_sync_status: MeetingCrmSyncStatus
    crm_sync_error: str | None = None
    crm_retry_after_seconds: int | None = None
    policy_snapshot: dict[str, object] = {}
    version: int
    created_at: datetime
    updated_at: datetime
    prep_packet: MeetingPrepPacketOut | None = None
    follow_up_tasks: list[MeetingFollowUpTaskOut] = []


class MeetingHandoffList(BaseModel):
    meetings: list[MeetingHandoffOut]


class ReportingMeetingList(BaseModel):
    metadata: ReportingMetadata
    meetings: list[MeetingHandoffOut]
    next_cursor: str | None = None


class ReportingMeetingDetail(BaseModel):
    metadata: ReportingMetadata
    meeting: MeetingHandoffOut
