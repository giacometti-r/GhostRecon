from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from .meetings import MeetingAttendee
from .sequence_definitions import SequenceActivityStatus, SequenceChannel


class SequenceActivityOut(BaseModel):
    id: str
    enrollment_id: str
    sequence_step_id: str
    outbound_email_id: str | None = None
    meeting_handoff_id: str | None = None
    sequence_id: str | None = None
    sequence_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    account_name: str | None = None
    step_order: int
    channel: SequenceChannel
    status: SequenceActivityStatus
    due_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    completed_by: str | None = None
    completed_at: datetime | None = None
    metadata: dict[str, object] = {}
    created_at: datetime
    updated_at: datetime


class SequenceActivityList(BaseModel):
    activities: list[SequenceActivityOut]


class SequenceActivityActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)
    metadata: dict[str, object] = {}


class SequenceActivityScheduleMeetingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str | None = Field(default=None, max_length=512)
    description: str | None = None
    location: str | None = Field(default="Google Meet", max_length=512)
    start_at: datetime
    end_at: datetime
    timezone: str = "UTC"
    attendees: list[MeetingAttendee] = []
    send_updates: bool | None = None
