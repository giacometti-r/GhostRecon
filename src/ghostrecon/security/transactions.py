from __future__ import annotations

import base64
import json
from dataclasses import asdict
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from redis.asyncio import Redis

from .jwt import TokenValidationError
from .oidc import OIDCTransaction


class OIDCTransactionRepository:
    def __init__(
        self,
        redis: Redis,
        *,
        encryption_key: str,
        ttl_seconds: int = 600,
        namespace: str = "ghostrecon:security:oidc",
    ) -> None:
        if len(encryption_key.encode()) < 32:
            raise ValueError("OIDC transaction key must contain at least 256 bits")
        raw_key = base64.urlsafe_b64encode(
            __import__("hashlib").sha256(encryption_key.encode()).digest()
        )
        self.fernet = Fernet(raw_key)
        self.redis = redis
        self.ttl_seconds = ttl_seconds
        self.namespace = namespace

    async def put(self, transaction: OIDCTransaction) -> None:
        payload = asdict(transaction)
        payload["created_at"] = transaction.created_at.isoformat()
        encrypted = self.fernet.encrypt(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        )
        state_key = self._state_key(transaction.state)
        browser_key = self._browser_key(transaction.browser_binding)
        previous = await self.redis.get(browser_key)
        pipeline = self.redis.pipeline(transaction=True)
        if previous:
            pipeline.delete(self._state_key(previous.decode()))
        pipeline.set(state_key, encrypted, ex=self.ttl_seconds, nx=True)
        pipeline.set(browser_key, transaction.state, ex=self.ttl_seconds)
        results = await pipeline.execute()
        if results[-2] is not True:
            raise TokenValidationError("OIDC transaction collision")

    async def consume(self, *, state: str, browser_binding: str) -> OIDCTransaction:
        if not state or not browser_binding:
            raise TokenValidationError("missing OIDC transaction")
        state_key = self._state_key(state)
        browser_key = self._browser_key(browser_binding)
        script = """
        local expected = redis.call('GET', KEYS[2])
        if not expected or expected ~= ARGV[1] then return false end
        local value = redis.call('GETDEL', KEYS[1])
        redis.call('DEL', KEYS[2])
        return value
        """
        encrypted = await self.redis.eval(script, 2, state_key, browser_key, state)
        if not encrypted:
            raise TokenValidationError("invalid or replayed OIDC transaction")
        try:
            payload = json.loads(self.fernet.decrypt(encrypted))
            return OIDCTransaction(
                state=payload["state"],
                nonce=payload["nonce"],
                code_verifier=payload["code_verifier"],
                browser_binding=payload["browser_binding"],
                return_path=payload["return_path"],
                created_at=datetime.fromisoformat(payload["created_at"]),
                purpose=payload.get("purpose", "login"),
                existing_session_id=payload.get("existing_session_id"),
            )
        except (InvalidToken, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise TokenValidationError("invalid OIDC transaction") from exc

    def _state_key(self, state: str) -> str:
        return f"{self.namespace}:state:{state}"

    def _browser_key(self, binding: str) -> str:
        return f"{self.namespace}:browser:{binding}"


class RedisReplayDetector:
    def __init__(self, redis: Redis, *, namespace: str = "ghostrecon:security:replay") -> None:
        self.redis = redis
        self.namespace = namespace

    async def consume(self, *, purpose: str, jti: str, expires_in_seconds: int) -> bool:
        if not purpose or not jti or expires_in_seconds <= 0:
            return False
        key = f"{self.namespace}:{purpose}:{jti}"
        return bool(await self.redis.set(key, "1", ex=expires_in_seconds, nx=True))
