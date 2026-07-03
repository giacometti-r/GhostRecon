from collections.abc import Mapping
from typing import Any

import httpx

from ghostrecon.common.config import Settings


class AttioClient:
    """Minimal Attio REST client with token auth and retry-after handling."""

    def __init__(self, settings: Settings) -> None:
        if not settings.attio_access_token:
            raise ValueError("GHOSTRECON_ATTIO_ACCESS_TOKEN is required for Attio API calls")
        self.settings = settings
        self.base_url = str(settings.attio_base_url).rstrip("/")

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.settings.attio_access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                json=json,
                params=params,
                headers=headers,
            )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "unknown")
                raise RuntimeError(f"Attio rate limit exceeded; retry after {retry_after}")
            response.raise_for_status()
            return response.json()
