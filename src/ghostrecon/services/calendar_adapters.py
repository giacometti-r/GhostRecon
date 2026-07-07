from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from ghostrecon.common.config import Settings
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

    async def create_event(self, request: CalendarEventRequest) -> CalendarEventResult:
        ...

    async def update_event(
        self,
        provider_event_id: str,
        request: CalendarEventRequest,
    ) -> CalendarEventResult:
        ...

    async def cancel_event(
        self,
        provider_event_id: str,
        *,
        send_updates: bool = True,
    ) -> None:
        ...

    async def get_availability(
        self,
        *,
        attendees: list[str],
        time_min: datetime,
        time_max: datetime,
        timezone: str,
    ) -> dict[str, list[CalendarBusySlot]]:
        ...


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
            raw_response={"id": event_id, "htmlLink": f"https://calendar.google.com/fake/{event_id}"},
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


class GoogleCalendarClient:
    provider = "google"
    token_url = "https://oauth2.googleapis.com/token"  # noqa: S105
    calendar_api_base = "https://www.googleapis.com/calendar/v3"
    scopes = (
        "https://www.googleapis.com/auth/calendar.events "
        "https://www.googleapis.com/auth/calendar.freebusy"
    )

    def __init__(self, settings: Settings) -> None:
        if not settings.google_calendar_id:
            raise ValueError("GHOSTRECON_GOOGLE_CALENDAR_ID is required")
        if not settings.google_client_email:
            raise ValueError("GHOSTRECON_GOOGLE_CLIENT_EMAIL is required")
        if not settings.google_private_key:
            raise ValueError("GHOSTRECON_GOOGLE_PRIVATE_KEY is required")
        self.settings = settings
        self.calendar_id = settings.google_calendar_id
        self.client_email = settings.google_client_email
        self.private_key = settings.google_private_key.replace("\\n", "\n")
        self.delegated_subject = settings.google_delegated_subject
        self._access_token: str | None = None
        self._token_expires_at = datetime.min.replace(tzinfo=UTC)

    async def create_event(self, request: CalendarEventRequest) -> CalendarEventResult:
        payload = await self._request(
            "POST",
            f"/calendars/{_path(self.calendar_id)}/events",
            params={
                "conferenceDataVersion": "1",
                "sendUpdates": _send_updates(request.send_updates),
            },
            json=_google_event_body(request),
        )
        return _event_result(payload, self.calendar_id)

    async def update_event(
        self,
        provider_event_id: str,
        request: CalendarEventRequest,
    ) -> CalendarEventResult:
        payload = await self._request(
            "PATCH",
            f"/calendars/{_path(self.calendar_id)}/events/{_path(provider_event_id)}",
            params={
                "conferenceDataVersion": "1",
                "sendUpdates": _send_updates(request.send_updates),
            },
            json=_google_event_body(request),
        )
        return _event_result(payload, self.calendar_id)

    async def cancel_event(
        self,
        provider_event_id: str,
        *,
        send_updates: bool = True,
    ) -> None:
        await self._request(
            "DELETE",
            f"/calendars/{_path(self.calendar_id)}/events/{_path(provider_event_id)}",
            params={"sendUpdates": _send_updates(send_updates)},
        )

    async def get_availability(
        self,
        *,
        attendees: list[str],
        time_min: datetime,
        time_max: datetime,
        timezone: str,
    ) -> dict[str, list[CalendarBusySlot]]:
        payload = await self._request(
            "POST",
            "/freeBusy",
            json={
                "timeMin": _iso(time_min),
                "timeMax": _iso(time_max),
                "timeZone": timezone,
                "items": [{"id": attendee.lower()} for attendee in attendees],
            },
        )
        calendars = payload.get("calendars") if isinstance(payload, dict) else {}
        if not isinstance(calendars, dict):
            return {}
        result: dict[str, list[CalendarBusySlot]] = {}
        for calendar_id, calendar_payload in calendars.items():
            if not isinstance(calendar_payload, dict):
                continue
            busy_slots = []
            for slot in calendar_payload.get("busy", []):
                if not isinstance(slot, dict):
                    continue
                start = _parse_datetime(slot.get("start"))
                end = _parse_datetime(slot.get("end"))
                if start and end:
                    busy_slots.append(CalendarBusySlot(start=start, end=end))
            result[str(calendar_id).lower()] = busy_slots
        return result

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = await self._token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.request(
                method,
                f"{self.calendar_api_base}{path}",
                params=params,
                json=json,
                headers=headers,
            )
            if response.status_code == 429:
                raise CalendarProviderError(
                    "Google Calendar rate limit exceeded",
                    retryable=True,
                    retry_after_seconds=_optional_int(response.headers.get("Retry-After")),
                )
            if response.status_code == 404:
                raise CalendarProviderError("Google Calendar resource not found")
            if response.status_code >= 500:
                raise CalendarProviderError(
                    f"Google Calendar request failed with status {response.status_code}",
                    retryable=True,
                )
            if response.status_code == 204:
                return {}
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise CalendarProviderError(
                    f"Google Calendar request failed with status {response.status_code}"
                ) from exc
            return response.json()

    async def _token(self) -> str:
        if self._access_token and datetime.now(UTC) < self._token_expires_at:
            return self._access_token
        assertion = self._jwt_assertion()
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
            if response.status_code >= 500 or response.status_code == 429:
                raise CalendarProviderError(
                    "Google OAuth token request failed",
                    retryable=response.status_code == 429 or response.status_code >= 500,
                    retry_after_seconds=_optional_int(response.headers.get("Retry-After")),
                )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise CalendarProviderError("Google OAuth token request was rejected") from exc
            payload = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise CalendarProviderError("Google OAuth token response did not include access_token")
        expires_in = int(payload.get("expires_in") or 3600)
        self._access_token = token
        self._token_expires_at = datetime.now(UTC) + timedelta(seconds=max(expires_in - 60, 60))
        return token

    def _jwt_assertion(self) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": self.client_email,
            "scope": self.scopes,
            "aud": self.token_url,
            "iat": now,
            "exp": now + 3600,
        }
        if self.delegated_subject:
            claims["sub"] = self.delegated_subject
        header = {"alg": "RS256", "typ": "JWT"}
        signing_input = (
            _b64(json.dumps(header, separators=(",", ":")).encode())
            + "."
            + _b64(json.dumps(claims, separators=(",", ":")).encode())
        )
        key = serialization.load_pem_private_key(self.private_key.encode(), password=None)
        signature = key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
        return signing_input + "." + _b64(signature)


def calendar_client_for_settings(settings: Settings) -> CalendarClient:
    if settings.environment == "local" and not (
        settings.google_calendar_id
        and settings.google_client_email
        and settings.google_private_key
    ):
        return FakeCalendarClient()
    return GoogleCalendarClient(settings)


def _google_event_body(request: CalendarEventRequest) -> dict[str, Any]:
    body: dict[str, Any] = {
        "summary": request.subject,
        "start": {"dateTime": _iso(request.start_at), "timeZone": request.timezone},
        "end": {"dateTime": _iso(request.end_at), "timeZone": request.timezone},
        "attendees": [
            {
                "email": str(attendee.email).lower(),
                "displayName": attendee.name,
                "optional": attendee.optional,
            }
            for attendee in request.attendees
        ],
        "extendedProperties": {"private": {"ghostrecon_meeting_id": request.meeting_id}},
    }
    if request.description:
        body["description"] = request.description
    if request.location:
        body["location"] = request.location
    return body


def _event_result(payload: dict[str, Any], calendar_id: str) -> CalendarEventResult:
    event_id = payload.get("id")
    if not isinstance(event_id, str) or not event_id:
        raise CalendarProviderError("Google Calendar response did not include event ID")
    html_link = payload.get("htmlLink") if isinstance(payload.get("htmlLink"), str) else None
    return CalendarEventResult(
        provider_event_id=event_id,
        calendar_id=calendar_id,
        html_link=html_link,
        raw_response=payload,
    )


def _send_updates(send_updates: bool) -> str:
    return "all" if send_updates else "none"


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _path(value: str) -> str:
    return quote(value, safe="")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
