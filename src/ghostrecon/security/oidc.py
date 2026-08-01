from __future__ import annotations

import base64
import hashlib
import json
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode, urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .jwt import TokenValidationError

MAX_PROVIDER_RESPONSE_BYTES = 1024 * 1024
SUPPORTED_EXTERNAL_ALGORITHMS = frozenset({"RS256", "RS384", "RS512"})


@dataclass(frozen=True, slots=True)
class OIDCTransaction:
    state: str
    nonce: str
    code_verifier: str
    browser_binding: str
    return_path: str
    created_at: datetime

    @classmethod
    def create(cls, return_path: str = "/") -> OIDCTransaction:
        return cls(
            state=secrets.token_urlsafe(32),
            nonce=secrets.token_urlsafe(32),
            code_verifier=secrets.token_urlsafe(64),
            browser_binding=secrets.token_urlsafe(32),
            return_path=validate_return_path(return_path),
            created_at=datetime.now(UTC),
        )

    @property
    def code_challenge(self) -> str:
        digest = hashlib.sha256(self.code_verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass(frozen=True, slots=True)
class OIDCProviderMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str

    @classmethod
    def parse(cls, payload: Mapping[str, Any], *, configured_issuer: str) -> OIDCProviderMetadata:
        issuer = _trusted_https_url(configured_issuer, "issuer").rstrip("/")
        if payload.get("issuer") != issuer:
            raise TokenValidationError("provider issuer mismatch")
        authorization_endpoint = _trusted_https_url(
            payload.get("authorization_endpoint"), "authorization endpoint"
        )
        token_endpoint = _trusted_https_url(payload.get("token_endpoint"), "token endpoint")
        jwks_uri = _trusted_https_url(payload.get("jwks_uri"), "JWKS endpoint")
        return cls(issuer, authorization_endpoint, token_endpoint, jwks_uri)


def discovery_url(issuer: str) -> str:
    return f"{_trusted_https_url(issuer, 'issuer').rstrip('/')}/.well-known/openid-configuration"


def authorization_url(
    metadata: OIDCProviderMetadata,
    transaction: OIDCTransaction,
    *,
    client_id: str,
    redirect_uri: str,
    scope: str = "openid email profile",
) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": transaction.state,
            "nonce": transaction.nonce,
            "code_challenge": transaction.code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{metadata.authorization_endpoint}?{query}"


def validate_return_path(path: str) -> str:
    parsed = urlparse(path)
    if not path.startswith("/") or path.startswith("//") or parsed.scheme or parsed.netloc:
        raise ValueError("return path must be a safe relative path")
    return path


def parse_bounded_json(content: bytes, *, maximum_bytes: int = MAX_PROVIDER_RESPONSE_BYTES) -> Any:
    if len(content) > maximum_bytes:
        raise TokenValidationError("provider response too large")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise TokenValidationError("invalid provider response") from exc


def verify_oidc_id_token(
    token: str,
    jwks: Mapping[str, Any],
    *,
    issuer: str,
    audience: str,
    nonce: str,
    allowed_algorithms: frozenset[str] = frozenset({"RS256"}),
    authorized_party: str | None = None,
    clock_skew_seconds: int = 30,
    now: datetime | None = None,
) -> Mapping[str, Any]:
    if not allowed_algorithms or not allowed_algorithms <= SUPPORTED_EXTERNAL_ALGORITHMS:
        raise ValueError("OIDC algorithms must be an explicit supported asymmetric allowlist")
    encoded_header, encoded_claims, encoded_signature = _split_token(token)
    header = _decode_json(encoded_header)
    claims = _decode_json(encoded_claims)
    algorithm = header.get("alg")
    if algorithm not in allowed_algorithms:
        raise TokenValidationError("invalid token algorithm")
    if header.get("typ") not in {None, "JWT"}:
        raise TokenValidationError("invalid token purpose")
    kid = header.get("kid")
    key = _select_rsa_key(jwks, kid=kid, algorithm=algorithm)
    hash_algorithm = {
        "RS256": hashes.SHA256,
        "RS384": hashes.SHA384,
        "RS512": hashes.SHA512,
    }[algorithm]()
    try:
        key.verify(
            _decode_segment(encoded_signature),
            f"{encoded_header}.{encoded_claims}".encode("ascii"),
            padding.PKCS1v15(),
            hash_algorithm,
        )
    except InvalidSignature as exc:
        raise TokenValidationError("invalid token signature") from exc
    _validate_oidc_claims(
        claims,
        issuer=issuer.rstrip("/"),
        audience=audience,
        nonce=nonce,
        authorized_party=authorized_party,
        clock_skew_seconds=clock_skew_seconds,
        now=now,
    )
    return claims


def _validate_oidc_claims(
    claims: Mapping[str, Any],
    *,
    issuer: str,
    audience: str,
    nonce: str,
    authorized_party: str | None,
    clock_skew_seconds: int,
    now: datetime | None,
) -> None:
    if claims.get("iss") != issuer:
        raise TokenValidationError("invalid token issuer")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise TokenValidationError("invalid token subject")
    token_audience = claims.get("aud")
    audiences = [token_audience] if isinstance(token_audience, str) else token_audience
    if not isinstance(audiences, list) or audience not in audiences:
        raise TokenValidationError("invalid token audience")
    azp = claims.get("azp")
    if len(audiences) > 1 and azp != audience:
        raise TokenValidationError("invalid authorized party")
    if authorized_party is not None and azp not in {None, authorized_party}:
        raise TokenValidationError("invalid authorized party")
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise TokenValidationError("invalid token nonce")
    current = int((now or datetime.now(UTC)).timestamp())
    try:
        issued_at = int(claims["iat"])
        expires_at = int(claims["exp"])
        not_before = int(claims.get("nbf", issued_at))
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenValidationError("invalid token time claims") from exc
    if issued_at > current + clock_skew_seconds or not_before > current + clock_skew_seconds:
        raise TokenValidationError("token is not active")
    if expires_at <= current - clock_skew_seconds:
        raise TokenValidationError("token expired")


def _select_rsa_key(
    jwks: Mapping[str, Any], *, kid: Any, algorithm: Any
) -> rsa.RSAPublicKey:
    if not isinstance(kid, str) or not kid:
        raise TokenValidationError("missing signing key identifier")
    keys = jwks.get("keys")
    if not isinstance(keys, list) or len(keys) > 100:
        raise TokenValidationError("invalid JWKS")
    for item in keys:
        if (
            isinstance(item, dict)
            and item.get("kid") == kid
            and item.get("kty") == "RSA"
            and item.get("use", "sig") == "sig"
            and item.get("alg", algorithm) == algorithm
        ):
            try:
                exponent = int.from_bytes(_decode_segment(item["e"]), "big")
                modulus = int.from_bytes(_decode_segment(item["n"]), "big")
                if modulus.bit_length() < 2048:
                    raise TokenValidationError("RSA signing key is too small")
                return rsa.RSAPublicNumbers(exponent, modulus).public_key()
            except (KeyError, TypeError, ValueError) as exc:
                raise TokenValidationError("invalid signing key") from exc
    raise TokenValidationError("unknown signing key")


def _trusted_https_url(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise TokenValidationError(f"invalid {label}")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise TokenValidationError(f"invalid {label}")
    return value


def _split_token(token: str) -> tuple[str, str, str]:
    try:
        first, second, third = token.split(".")
        return first, second, third
    except ValueError as exc:
        raise TokenValidationError("invalid token") from exc


def _decode_segment(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError) as exc:
        raise TokenValidationError("invalid token encoding") from exc


def _decode_json(value: str) -> Mapping[str, Any]:
    try:
        parsed = json.loads(_decode_segment(value))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TokenValidationError("invalid token") from exc
    if not isinstance(parsed, dict):
        raise TokenValidationError("invalid token")
    return parsed
