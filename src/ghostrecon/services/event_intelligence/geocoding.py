from __future__ import annotations

from ghostrecon.common.config import Settings
from ghostrecon.common.configuration import assert_adapter_allowed
from ghostrecon.models.api import (
    ManualEventCreate,
)
from ghostrecon.models.db import (
    CyberEvent,
)
from ghostrecon.services.geocoding import (
    Geocoder,
    GeocodeRequest,
    GeocodeResult,
    geocoder_for_settings,
)


async def _geocode_event_payload(
    payload: ManualEventCreate,
    settings: Settings,
    geocoder: Geocoder | None,
) -> GeocodeResult:
    if payload.event_format.value != "in-person":
        return GeocodeResult(None, None, "not_required")
    resolver = geocoder or geocoder_for_settings(settings)
    assert_adapter_allowed(settings, resolver, "geocoder_provider")
    return await resolver.geocode(
        GeocodeRequest(
            street_address=payload.street_address,
            city=payload.city,
            postcode=payload.postcode,
            country=payload.country,
        )
    )


async def _apply_event_geocode(
    event: CyberEvent,
    settings: Settings,
    geocoder: Geocoder | None,
) -> None:
    if event.event_format != "in-person":
        event.latitude = None
        event.longitude = None
        event.geocode_status = "not_required"
        event.geocode_provider = None
        event.geocode_display_name = None
        event.geocoded_at = None
        return
    if not (event.street_address and event.city and event.postcode and event.country):
        event.geocode_status = "insufficient_address"
        event.latitude = None
        event.longitude = None
        event.geocode_provider = None
        event.geocode_display_name = None
        event.geocoded_at = None
        return
    resolver = geocoder or geocoder_for_settings(settings)
    assert_adapter_allowed(settings, resolver, "geocoder_provider")
    result = await resolver.geocode(
        GeocodeRequest(
            street_address=event.street_address,
            city=event.city,
            postcode=event.postcode,
            country=event.country,
        )
    )
    event.latitude = result.latitude
    event.longitude = result.longitude
    event.geocode_status = result.status
    event.geocode_provider = result.provider
    event.geocode_display_name = result.display_name
    event.geocoded_at = result.geocoded_at
