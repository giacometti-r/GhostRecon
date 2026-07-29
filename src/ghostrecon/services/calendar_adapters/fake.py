from __future__ import annotations

from datetime import datetime
from typing import Any

from ghostrecon.models.api import CalendarBusySlot


class FakeCalendarClient:
    provider = "fake"

    def __init__(self, calendar_id: str = "fake-calendar") -> None:
        self.calendar_id = calendar_id
        self.events: dict[str, dict[str, Any]] = {}

    async def create_event(self, request: CalendarEventRequest) -> CalendarEventResult:
        event_id = f"fake-{request.meeting_id}"
        payload = _google_event_body(request)
        self.events[event_id] = payload
        return CalendarEventResult(
            provider_event_id=event_id,
            calendar_id=self.calendar_id,
            html_link=f"https://calendar.google.com/fake/{event_id}",
            raw_response={
                "id": event_id,
                "htmlLink": f"https://calendar.google.com/fake/{event_id}",
            },
        )

    async def update_event(
        self,
        provider_event_id: str,
        request: CalendarEventRequest,
    ) -> CalendarEventResult:
        payload = _google_event_body(request)
        self.events[provider_event_id] = payload
        return CalendarEventResult(
            provider_event_id=provider_event_id,
            calendar_id=self.calendar_id,
            html_link=f"https://calendar.google.com/fake/{provider_event_id}",
            raw_response={
                "id": provider_event_id,
                "htmlLink": f"https://calendar.google.com/fake/{provider_event_id}",
            },
        )

    async def cancel_event(
        self,
        provider_event_id: str,
        *,
        send_updates: bool = True,
    ) -> None:
        _ = send_updates
        self.events.pop(provider_event_id, None)

    async def get_availability(
        self,
        *,
        attendees: list[str],
        time_min: datetime,
        time_max: datetime,
        timezone: str,
    ) -> dict[str, list[CalendarBusySlot]]:
        _ = time_min, time_max, timezone
        return {attendee.lower(): [] for attendee in attendees}


from .base import CalendarEventRequest, CalendarEventResult  # noqa: E402
from .google import _google_event_body  # noqa: E402
