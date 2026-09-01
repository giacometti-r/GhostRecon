from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

SESSION_COOKIE_NAME = "__Host-ghostrecon_session"
TRANSACTION_COOKIE_NAME = "__Host-ghostrecon_oidc_transaction"
SESSION_IDENTIFIER_BYTES = 32


@dataclass(frozen=True, slots=True)
class SessionSecrets:
    identifier: str
    identifier_digest: str
    csrf_token: str
    csrf_digest: str


def create_session_secrets(hmac_key: bytes) -> SessionSecrets:
    if len(hmac_key) < 32:
        raise ValueError("session HMAC key must contain at least 256 bits")
    identifier = secrets.token_urlsafe(SESSION_IDENTIFIER_BYTES)
    csrf_token = secrets.token_urlsafe(SESSION_IDENTIFIER_BYTES)
    return SessionSecrets(
        identifier=identifier,
        identifier_digest=digest_secret(identifier, hmac_key),
        csrf_token=csrf_token,
        csrf_digest=digest_secret(csrf_token, hmac_key),
    )


def csrf_token_for_session(identifier: str, hmac_key: bytes) -> str:
    if len(hmac_key) < 32:
        raise ValueError("session HMAC key must contain at least 256 bits")
    return hmac.new(hmac_key, f"{identifier}:csrf".encode(), hashlib.sha256).hexdigest()


def digest_secret(value: str, hmac_key: bytes) -> str:
    return hmac.new(hmac_key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_secret(value: str | None, expected_digest: str, hmac_key: bytes) -> bool:
    if not value:
        return False
    return hmac.compare_digest(digest_secret(value, hmac_key), expected_digest)
