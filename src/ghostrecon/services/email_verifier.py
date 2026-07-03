from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import EmailStr

from ghostrecon.common.config import Settings


class EmailVerifierClient:
    """HTTP adapter for the umuterturk/email-verifier sidecar service."""

    def __init__(self, settings: Settings) -> None:
        self.base_url = str(settings.email_verifier_url).rstrip("/")

    async def validate(self, email: EmailStr) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.base_url}/api/validate", json={"email": str(email)}
            )
            response.raise_for_status()
            return response.json()

    async def validate_batch(self, emails: Sequence[EmailStr]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/api/validate/batch",
                json={"emails": [str(email) for email in emails]},
            )
            response.raise_for_status()
            return response.json()
