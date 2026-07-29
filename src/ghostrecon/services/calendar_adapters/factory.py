from __future__ import annotations

from ghostrecon.common.config import Settings
from ghostrecon.common.configuration import (
    CalendarProvider,
    assert_adapter_allowed,
)


def calendar_client_for_settings(settings: Settings) -> CalendarClient:
    if settings.calendar_provider == CalendarProvider.FAKE:
        client: CalendarClient = FakeCalendarClient()
    elif settings.calendar_provider == CalendarProvider.GOOGLE:
        client = GoogleCalendarClient(settings)
    else:
        raise ValueError("calendar provider is disabled")
    assert_adapter_allowed(settings, client, "calendar_provider")
    return client


from .base import CalendarClient  # noqa: E402
from .fake import FakeCalendarClient  # noqa: E402
from .google import GoogleCalendarClient  # noqa: E402
