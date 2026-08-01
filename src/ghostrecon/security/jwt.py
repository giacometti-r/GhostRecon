from __future__ import annotations

import base64
import json
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


class TokenValidationError(ValueError):
    """A deliberately redacted credential validation failure."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError) as exc:
        raise TokenValidationError("invalid token encoding") from exc


def _json_segment(value: Mapping[str, Any]) -> str:
    return _encode(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    )


@dataclass(frozen=True, slots=True)
class VerifiedToken:
    header: Mapping[str, Any]
    claims: Mapping[str, Any]


def sign_eddsa(
    claims: Mapping[str, Any],
    private_key: Ed25519PrivateKey,
    *,
    kid: str,
    token_type: str,
) -> str:
    header = {"alg": "EdDSA", "kid": kid, "typ": token_type}
    encoded_header = _json_segment(header)
    encoded_claims = _json_segment(claims)
    signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
    return f"{encoded_header}.{encoded_claims}.{_encode(private_key.sign(signing_input))}"


def verify_eddsa(
    token: str,
    public_keys: Mapping[str, Ed25519PublicKey],
    *,
    expected_type: str,
    issuer: str,
    audience: str,
    subject: str | None = None,
    maximum_lifetime_seconds: int = 300,
    clock_skew_seconds: int = 30,
    now: datetime | None = None,
) -> VerifiedToken:
    try:
        encoded_header, encoded_claims, encoded_signature = token.split(".")
        header = json.loads(_decode(encoded_header))
        claims = json.loads(_decode(encoded_claims))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise TokenValidationError("invalid token") from exc
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise TokenValidationError("invalid token")
    if header.get("alg") != "EdDSA" or header.get("typ") != expected_type:
        raise TokenValidationError("invalid token purpose")
    kid = header.get("kid")
    if not isinstance(kid, str) or kid not in public_keys:
        raise TokenValidationError("unknown signing key")
    try:
        public_keys[kid].verify(
            _decode(encoded_signature),
            f"{encoded_header}.{encoded_claims}".encode("ascii"),
        )
    except InvalidSignature as exc:
        raise TokenValidationError("invalid token signature") from exc

    current = int((now or datetime.now(UTC)).timestamp())
    token_issuer = claims.get("iss")
    token_subject = claims.get("sub")
    if token_issuer != issuer or not isinstance(token_subject, str) or not token_subject:
        raise TokenValidationError("invalid token identity")
    if subject is not None and token_subject != subject:
        raise TokenValidationError("invalid token identity")
    token_audience = claims.get("aud")
    audiences = [token_audience] if isinstance(token_audience, str) else token_audience
    if not isinstance(audiences, list) or audience not in audiences:
        raise TokenValidationError("invalid token audience")
    try:
        issued_at = int(claims["iat"])
        not_before = int(claims["nbf"])
        expires_at = int(claims["exp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenValidationError("invalid token time claims") from exc
    if issued_at > current + clock_skew_seconds or not_before > current + clock_skew_seconds:
        raise TokenValidationError("token is not active")
    if expires_at <= current - clock_skew_seconds:
        raise TokenValidationError("token expired")
    if expires_at <= issued_at or expires_at - issued_at > maximum_lifetime_seconds:
        raise TokenValidationError("invalid token lifetime")
    if not isinstance(claims.get("jti"), str) or not claims["jti"]:
        raise TokenValidationError("missing token identifier")
    return VerifiedToken(header=header, claims=claims)


def service_claims(
    *,
    workload: str,
    environment: str,
    receiver: str,
    lifetime_seconds: int = 120,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not 1 <= lifetime_seconds <= 300:
        raise ValueError("service token lifetime must be between 1 and 300 seconds")
    issued = now or datetime.now(UTC)
    principal = f"urn:ghostrecon:{environment}:workload:{workload}"
    return {
        "iss": principal,
        "sub": principal,
        "aud": f"urn:ghostrecon:{environment}:service:{receiver}",
        "iat": int(issued.timestamp()),
        "nbf": int((issued - timedelta(seconds=1)).timestamp()),
        "exp": int((issued + timedelta(seconds=lifetime_seconds)).timestamp()),
        "jti": secrets.token_urlsafe(24),
    }


def obo_claims(
    *,
    gateway_principal: str,
    human_subject: str,
    audience: str,
    operation: str,
    correlation_id: str,
    assurance: str,
    authentication_method: str,
    authenticated_at: datetime,
    mapping_version: str,
    policy_version: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    issued = now or datetime.now(UTC)
    return {
        "iss": gateway_principal,
        "sub": human_subject,
        "azp": gateway_principal,
        "aud": audience,
        "operation": operation,
        "correlation_id": correlation_id,
        "assurance": assurance,
        "authentication_method": authentication_method,
        "authenticated_at": int(authenticated_at.timestamp()),
        "mapping_version": mapping_version,
        "policy_version": policy_version,
        "iat": int(issued.timestamp()),
        "nbf": int((issued - timedelta(seconds=1)).timestamp()),
        "exp": int((issued + timedelta(seconds=45)).timestamp()),
        "jti": secrets.token_urlsafe(24),
    }
