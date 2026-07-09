import pytest

from ghostrecon.common.config import Settings
from ghostrecon.services.geocoding import (
    GeocodeRequest,
    LocalDemoGeocoder,
    NominatimGeocoder,
)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    last_headers = None
    last_params = None

    def __init__(self, *, headers, timeout, follow_redirects):
        self.headers = headers
        self.timeout = timeout
        self.follow_redirects = follow_redirects
        _FakeAsyncClient.last_headers = headers

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, *, params):
        _FakeAsyncClient.last_params = params
        return _FakeResponse(
            [
                {
                    "lat": "47.3769",
                    "lon": "8.5417",
                    "display_name": "Demo Convention Center",
                }
            ]
        )


@pytest.mark.asyncio
async def test_local_demo_geocoder_resolves_seeded_venue() -> None:
    result = await LocalDemoGeocoder().geocode(
        GeocodeRequest(
            street_address="Demo Way 42",
            city="Zurich",
            postcode="8001",
            country="CH",
        )
    )

    assert result.status == "resolved"
    assert result.provider == "local_demo"
    assert result.latitude == 47.3769
    assert result.longitude == 8.5417


@pytest.mark.asyncio
async def test_nominatim_geocoder_uses_structured_query_and_user_agent() -> None:
    geocoder = NominatimGeocoder(
        Settings(
            nominatim_base_url="https://nominatim.example",
            nominatim_user_agent="GhostRecon Tests/1.0",
        ),
        client_factory=_FakeAsyncClient,
    )

    result = await geocoder.geocode(
        GeocodeRequest(
            street_address="Demo Way 42",
            city="Zurich",
            postcode="8001",
            country="CH",
        )
    )

    assert result.status == "resolved"
    assert result.provider == "nominatim"
    assert _FakeAsyncClient.last_headers == {"User-Agent": "GhostRecon Tests/1.0"}
    assert _FakeAsyncClient.last_params == {
        "format": "jsonv2",
        "limit": 1,
        "street": "Demo Way 42",
        "city": "Zurich",
        "postalcode": "8001",
        "country": "CH",
    }
