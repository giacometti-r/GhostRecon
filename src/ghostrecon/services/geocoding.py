from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import httpx

from ghostrecon.common.config import Settings


@dataclass(frozen=True)
class GeocodeRequest:
    street_address: str | None = None
    city: str | None = None
    postcode: str | None = None
    country: str | None = None


@dataclass(frozen=True)
class GeocodeResult:
    latitude: float | None
    longitude: float | None
    status: str
    provider: str | None = None
    display_name: str | None = None
    geocoded_at: datetime | None = None


class Geocoder(Protocol):
    async def geocode(self, request: GeocodeRequest) -> GeocodeResult:
        """Resolve a structured address to coordinates."""


class DisabledGeocoder:
    async def geocode(self, request: GeocodeRequest) -> GeocodeResult:
        _ = request
        return GeocodeResult(None, None, "not_configured")


class LocalDemoGeocoder:
    _COORDINATES = {
        ("demo way 42", "zurich", "8001", "ch"): (
            47.3769,
            8.5417,
            "Demo Convention Center, Demo Way 42, 8001 Zurich, Switzerland",
        ),
        ("3950 las vegas blvd s", "las vegas", "89119", "us"): (
            36.0908,
            -115.1761,
            "Mandalay Bay, 3950 Las Vegas Blvd S, Las Vegas, NV 89119, USA",
        ),
    }

    async def geocode(self, request: GeocodeRequest) -> GeocodeResult:
        key = (
            _normalize(request.street_address),
            _normalize(request.city),
            _normalize(request.postcode),
            _normalize(request.country),
        )
        match = self._COORDINATES.get(key)
        if match is None:
            return GeocodeResult(None, None, "not_found", provider="local_demo")
        lat, lon, display_name = match
        return GeocodeResult(
            lat,
            lon,
            "resolved",
            provider="local_demo",
            display_name=display_name,
            geocoded_at=datetime.now(UTC),
        )


class NominatimGeocoder:
    def __init__(
        self,
        settings: Settings,
        client_factory: type[httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        self.base_url = str(settings.nominatim_base_url).rstrip("/")
        self.user_agent = settings.nominatim_user_agent
        self.client_factory = client_factory

    async def geocode(self, request: GeocodeRequest) -> GeocodeResult:
        params = {
            "format": "jsonv2",
            "limit": 1,
            "street": request.street_address,
            "city": request.city,
            "postalcode": request.postcode,
            "country": request.country,
        }
        params = {key: value for key, value in params.items() if value not in (None, "")}
        if len(params) <= 2:
            return GeocodeResult(None, None, "insufficient_address", provider="nominatim")
        try:
            async with self.client_factory(
                timeout=10,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            ) as client:
                response = await client.get(
                    f"{self.base_url}/search",
                    params=params,
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return GeocodeResult(None, None, "failed", provider="nominatim")
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            return GeocodeResult(None, None, "not_found", provider="nominatim")
        first = payload[0]
        try:
            latitude = float(first["lat"])
            longitude = float(first["lon"])
        except (KeyError, TypeError, ValueError):
            return GeocodeResult(None, None, "failed", provider="nominatim")
        return GeocodeResult(
            latitude,
            longitude,
            "resolved",
            provider="nominatim",
            display_name=str(first.get("display_name") or ""),
            geocoded_at=datetime.now(UTC),
        )


def geocoder_for_settings(settings: Settings) -> Geocoder:
    if settings.geocoder_provider == "nominatim":
        return NominatimGeocoder(settings)
    if settings.geocoder_provider == "local_demo":
        return LocalDemoGeocoder()
    return DisabledGeocoder()


def _normalize(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())
