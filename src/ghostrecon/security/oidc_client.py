from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from time import monotonic
from typing import Any

import httpx

from ghostrecon.common.config import Settings

from .jwt import TokenValidationError
from .oidc import (
    OIDCProviderMetadata,
    discovery_url,
    parse_bounded_json,
    verify_oidc_id_token,
)


@dataclass(frozen=True, slots=True)
class OIDCTokenResult:
    claims: Mapping[str, Any]
    authentication_method: str


class OIDCClient:
    """Bounded OIDC discovery, JWKS, and code exchange client.

    Provider credentials and raw tokens live only for the duration of callback
    processing and are never returned to routes or persistence code.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not settings.oidc_issuer or not settings.oidc_client_id:
            raise ValueError("OIDC issuer and client ID are required")
        self.settings = settings
        self.transport = transport
        self._metadata: tuple[float, OIDCProviderMetadata] | None = None
        self._jwks: tuple[float, Mapping[str, Any]] | None = None
        self._refresh_lock = asyncio.Lock()

    async def metadata(self) -> OIDCProviderMetadata:
        if self._metadata and self._metadata[0] > monotonic():
            return self._metadata[1]
        payload = await self._get_json(discovery_url(self.settings.oidc_issuer or ""))
        if not isinstance(payload, Mapping):
            raise TokenValidationError("invalid provider metadata")
        value = OIDCProviderMetadata.parse(
            payload, configured_issuer=self.settings.oidc_issuer or ""
        )
        self._metadata = (monotonic() + self.settings.oidc_jwks_cache_seconds, value)
        return value

    async def jwks(self, *, force: bool = False) -> Mapping[str, Any]:
        if not force and self._jwks and self._jwks[0] > monotonic():
            return self._jwks[1]
        async with self._refresh_lock:
            if not force and self._jwks and self._jwks[0] > monotonic():
                return self._jwks[1]
            metadata = await self.metadata()
            payload = await self._get_json(metadata.jwks_uri)
            if not isinstance(payload, Mapping):
                raise TokenValidationError("invalid JWKS")
            self._jwks = (monotonic() + self.settings.oidc_jwks_cache_seconds, payload)
            return payload

    async def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        nonce: str,
    ) -> OIDCTokenResult:
        if not code or len(code) > 4096:
            raise TokenValidationError("invalid authorization code")
        metadata = await self.metadata()
        form = {
            "grant_type": "authorization_code",
            "client_id": self.settings.oidc_client_id or "",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": self.settings.oidc_redirect_uri or "",
        }
        if self.settings.oidc_client_secret:
            form["client_secret"] = self.settings.oidc_client_secret
        async with httpx.AsyncClient(
            timeout=self.settings.oidc_metadata_timeout_seconds,
            transport=self.transport,
            follow_redirects=False,
        ) as client:
            response = await client.post(metadata.token_endpoint, data=form)
            content = await _bounded_content(
                response, maximum_bytes=self.settings.oidc_provider_maximum_bytes
            )
        if response.status_code != 200:
            raise TokenValidationError("OIDC code exchange failed")
        payload = parse_bounded_json(
            content, maximum_bytes=self.settings.oidc_provider_maximum_bytes
        )
        if not isinstance(payload, Mapping) or not isinstance(payload.get("id_token"), str):
            raise TokenValidationError("invalid OIDC token response")
        claims = await self._verify_with_rotation(payload["id_token"], nonce=nonce)
        for required in self.settings.oidc_required_claims:
            if required not in claims:
                raise TokenValidationError("missing required identity claim")
        if claims.get("email_verified") is not True:
            raise TokenValidationError("email is not verified")
        return OIDCTokenResult(
            claims=claims,
            authentication_method=_authentication_method(claims),
        )

    async def _verify_with_rotation(self, token: str, *, nonce: str) -> Mapping[str, Any]:
        parameters = {
            "issuer": self.settings.oidc_issuer or "",
            "audience": self.settings.oidc_client_id or "",
            "nonce": nonce,
            "allowed_algorithms": frozenset(self.settings.oidc_allowed_algorithms),
            "authorized_party": self.settings.oidc_client_id,
        }
        try:
            return verify_oidc_id_token(token, await self.jwks(), **parameters)
        except TokenValidationError as exc:
            if str(exc) != "unknown signing key":
                raise
        return verify_oidc_id_token(token, await self.jwks(force=True), **parameters)

    async def _get_json(self, url: str) -> Any:
        async with httpx.AsyncClient(
            timeout=self.settings.oidc_metadata_timeout_seconds,
            transport=self.transport,
            follow_redirects=False,
        ) as client:
            response = await client.get(url, headers={"Accept": "application/json"})
            content = await _bounded_content(
                response, maximum_bytes=self.settings.oidc_provider_maximum_bytes
            )
        if response.status_code != 200:
            raise TokenValidationError("provider metadata unavailable")
        return parse_bounded_json(
            content, maximum_bytes=self.settings.oidc_provider_maximum_bytes
        )


async def _bounded_content(response: httpx.Response, *, maximum_bytes: int) -> bytes:
    content = bytearray()
    async for chunk in response.aiter_bytes():
        content.extend(chunk)
        if len(content) > maximum_bytes:
            raise TokenValidationError("provider response too large")
    return bytes(content)


def _authentication_method(claims: Mapping[str, Any]) -> str:
    methods = claims.get("amr")
    if not isinstance(methods, list):
        return "oidc"
    safe = sorted({str(item)[:64] for item in methods if isinstance(item, str)})
    return "+".join(safe) or "oidc"
