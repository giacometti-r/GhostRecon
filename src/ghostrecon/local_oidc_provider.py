"""Guarded local/test OIDC provider for deterministic browser contracts."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlencode

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from ghostrecon.common.config import Settings

settings = Settings()
if settings.strict_runtime:
    raise RuntimeError("the local OIDC provider cannot run in staging or production")

ISSUER = "http://local-oidc:8080"
CLIENT_ID = "ghostrecon-local"
KEY_ID = "local-ephemeral"
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_codes: dict[str, dict[str, str]] = {}

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/.well-known/openid-configuration")
async def discovery() -> dict[str, object]:
    return {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "jwks_uri": f"{ISSUER}/jwks",
        "response_types_supported": ["code"],
        "code_challenge_methods_supported": ["S256"],
        "id_token_signing_alg_values_supported": ["RS256"],
    }


@app.get("/jwks")
async def jwks() -> dict[str, object]:
    numbers = _private_key.public_key().public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": KEY_ID,
                "use": "sig",
                "alg": "RS256",
                "n": _encode(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
                "e": _encode(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
            }
        ]
    }


@app.get("/authorize")
async def authorize(request: Request) -> RedirectResponse:
    query = request.query_params
    required = ("client_id", "redirect_uri", "state", "nonce", "code_challenge")
    if any(not query.get(name) for name in required) or query.get("client_id") != CLIENT_ID:
        raise HTTPException(status_code=400, detail="invalid authorization request")
    if query.get("code_challenge_method") != "S256":
        raise HTTPException(status_code=400, detail="PKCE S256 is required")
    code = secrets.token_urlsafe(32)
    _codes[code] = {
        "nonce": query["nonce"],
        "challenge": query["code_challenge"],
        "redirect_uri": query["redirect_uri"],
    }
    return RedirectResponse(
        f"{query['redirect_uri']}?{urlencode({'code': code, 'state': query['state']})}",
        status_code=303,
    )


@app.post("/token")
async def token(request: Request) -> JSONResponse:
    form = parse_qs((await request.body()).decode())
    code = _one(form, "code")
    verifier = _one(form, "code_verifier")
    redirect_uri = _one(form, "redirect_uri")
    transaction = _codes.pop(code, None)
    challenge = _encode(hashlib.sha256(verifier.encode()).digest())
    if (
        transaction is None
        or not secrets.compare_digest(challenge, transaction["challenge"])
        or redirect_uri != transaction["redirect_uri"]
    ):
        raise HTTPException(status_code=400, detail="invalid or replayed code")
    now = datetime.now(UTC)
    claims = {
        "iss": ISSUER,
        "sub": "local-development-user",
        "aud": CLIENT_ID,
        "azp": CLIENT_ID,
        "nonce": transaction["nonce"],
        "email": "local-admin@ghostrecon.invalid",
        "email_verified": True,
        "amr": ["webauthn"],
        "auth_time": int(now.timestamp()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "https://ghostrecon.example/roles": ["administrator"],
    }
    return JSONResponse(
        {"token_type": "Bearer", "expires_in": 300, "id_token": _jwt(claims)}  # nosec B105
    )


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _jwt(claims: dict[str, object]) -> str:
    header = _encode_json({"alg": "RS256", "kid": KEY_ID, "typ": "JWT"})
    payload = _encode_json(claims)
    signature = _private_key.sign(
        f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256()
    )
    return f"{header}.{payload}.{_encode(signature)}"


def _encode_json(value: dict[str, object]) -> str:
    return _encode(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _one(form: dict[str, list[str]], name: str) -> str:
    values = form.get(name)
    if not values or len(values) != 1:
        raise HTTPException(status_code=400, detail="invalid token request")
    return values[0]
