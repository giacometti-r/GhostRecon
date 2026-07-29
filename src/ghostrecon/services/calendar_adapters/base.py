from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from ghostrecon.models.api import CalendarBusySlot, MeetingAttendee


class CalendarProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class CalendarEventRequest:
    meeting_id: str
    subject: str
    start_at: datetime
    end_at: datetime
    timezone: str
    attendees: list[MeetingAttendee]
    description: str | None = None
    location: str | None = None
    send_updates: bool = True


@dataclass(frozen=True)
class CalendarEventResult:
    provider_event_id: str
    calendar_id: str
    html_link: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


class CalendarClient(Protocol):
    provider: str

    async def create_event(self, request: CalendarEventRequest) -> CalendarEventResult: ...

    async def update_event(
        self,
        provider_event_id: str,
        request: CalendarEventRequest,
    ) -> CalendarEventResult: ...

    async def cancel_event(
        self,
        provider_event_id: str,
        *,
        send_updates: bool = True,
    ) -> None: ...

    async def get_availability(
        self,
        *,
        attendees: list[str],
        time_min: datetime,
        time_max: datetime,
        timezone: str,
    ) -> dict[str, list[CalendarBusySlot]]: ...
