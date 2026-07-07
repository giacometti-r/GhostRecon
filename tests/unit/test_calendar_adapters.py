import re
from datetime import UTC, datetime

import httpx
import pytest
import respx

from ghostrecon.common.config import Settings
from ghostrecon.models.api import MeetingAttendee
from ghostrecon.services.calendar_adapters import (
    CalendarEventRequest,
    CalendarProviderError,
    GoogleCalendarClient,
)

NOW = datetime(2026, 7, 7, 15, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(
        environment="prod",
        google_calendar_id="primary",
        google_client_email="calendar@example.iam.gserviceaccount.com",
        google_private_key="unit-test-key",
    )


def _event_request(send_updates: bool = True) -> CalendarEventRequest:
    return CalendarEventRequest(
        meeting_id="meeting-1",
        subject="Security discovery",
        start_at=NOW,
        end_at=NOW.replace(hour=16),
        timezone="UTC",
        attendees=[MeetingAttendee(email="ada@example.com", name="Ada Lovelace")],
        description="Discuss incident follow-up.",
        send_updates=send_updates,
    )


@pytest.mark.asyncio
@respx.mock
async def test_google_calendar_client_inserts_event_with_service_account_token(monkeypatch) -> None:
    monkeypatch.setattr(GoogleCalendarClient, "_jwt_assertion", lambda self: "assertion")
    token_route = respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(200, json={"access_token": "token-1", "expires_in": 3600})
    )
    event_route = respx.post(
        re.compile(r"https://www\.googleapis\.com/calendar/v3/calendars/primary/events.*")
    ).mock(
        return_value=httpx.Response(
            200,
            json={"id": "google-event-1", "htmlLink": "https://calendar.google.com/event"},
        )
    )
    client = GoogleCalendarClient(_settings())

    result = await client.create_event(_event_request())

    assert result.provider_event_id == "google-event-1"
    assert result.html_link == "https://calendar.google.com/event"
    assert "assertion=assertion" in token_route.calls[0].request.content.decode()
    event_request = event_route.calls[0].request
    assert event_request.headers["Authorization"] == "Bearer token-1"
    assert "sendUpdates=all" in str(event_request.url)
    assert event_request.content


@pytest.mark.asyncio
@respx.mock
async def test_google_calendar_freebusy_maps_busy_slots(monkeypatch) -> None:
    monkeypatch.setattr(GoogleCalendarClient, "_jwt_assertion", lambda self: "assertion")
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(200, json={"access_token": "token-1", "expires_in": 3600})
    )
    respx.post("https://www.googleapis.com/calendar/v3/freeBusy").mock(
        return_value=httpx.Response(
            200,
            json={
                "calendars": {
                    "ada@example.com": {
                        "busy": [
                            {
                                "start": "2026-07-07T15:00:00Z",
                                "end": "2026-07-07T16:00:00Z",
                            }
                        ]
                    }
                }
            },
        )
    )
    client = GoogleCalendarClient(_settings())

    result = await client.get_availability(
        attendees=["ada@example.com"],
        time_min=NOW,
        time_max=NOW.replace(hour=17),
        timezone="UTC",
    )

    assert result["ada@example.com"][0].start == NOW
    assert result["ada@example.com"][0].end == NOW.replace(hour=16)


@pytest.mark.asyncio
@respx.mock
async def test_google_calendar_rate_limit_is_retryable(monkeypatch) -> None:
    monkeypatch.setattr(GoogleCalendarClient, "_jwt_assertion", lambda self: "assertion")
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(200, json={"access_token": "token-1", "expires_in": 3600})
    )
    respx.post(
        re.compile(r"https://www\.googleapis\.com/calendar/v3/calendars/primary/events.*")
    ).mock(return_value=httpx.Response(429, headers={"Retry-After": "30"}))
    client = GoogleCalendarClient(_settings())

    with pytest.raises(CalendarProviderError) as exc:
        await client.create_event(_event_request())

    assert exc.value.retryable is True
    assert exc.value.retry_after_seconds == 30
