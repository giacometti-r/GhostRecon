from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware

from ghostrecon.common.config import Settings

from .perimeter import security_error

_LIMITS = {
    "auth": (5, 60, True),
    "callback": (20, 60, True),
    "session": (60, 60, True),
    "read": (300, 60, False),
    "mutation": (60, 60, True),
    "bulk": (10, 60, True),
    "owner": (600, 60, True),
}


class DistributedRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self.redis = Redis.from_url(str(settings.redis_url), decode_responses=True)
        self.local: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not self.settings.strict_runtime or request.url.path == "/healthz":
            return await call_next(request)
        rate_class = self._classify(request)
        limit, window, fail_closed = _LIMITS[rate_class]
        identity = getattr(request.state, "identity", None)
        subject = (
            identity.represented_subject
            if identity is not None
            else (request.client.host if request.client else "unknown")
        )
        bucket = int(time.time()) // window
        key = f"ghostrecon:rate:{rate_class}:{subject}:{bucket}"
        try:
            count = int(
                await self.redis.eval(
                    "local v=redis.call('INCR',KEYS[1]); "
                    "if v==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return v",
                    1,
                    key,
                    window + 1,
                )
            )
        except Exception:
            if fail_closed:
                return security_error(
                    status_code=503,
                    code="rate_limit_unavailable",
                    message="security rate limiting is temporarily unavailable",
                    correlation_id=request.state.correlation_id,
                )
            count = self._local_count(key, window)
        if count > limit:
            response = security_error(
                status_code=429,
                code="rate_limit_exceeded",
                message="request rate limit exceeded",
                correlation_id=request.state.correlation_id,
            )
            response.headers["Retry-After"] = str(window)
            return response
        return await call_next(request)

    def _classify(self, request: Request) -> str:
        path = request.url.path
        if path == "/auth/callback":
            return "callback"
        if path.startswith("/auth/"):
            return "session" if path.startswith("/auth/session") else "auth"
        if "bulk" in path or "export" in path:
            return "bulk"
        if self.settings.service_name.value != "gateway-service":
            return "owner"
        return "read" if request.method in {"GET", "HEAD", "OPTIONS"} else "mutation"

    def _local_count(self, key: str, window: int) -> int:
        count, expires = self.local[key]
        now = time.monotonic()
        if expires <= now:
            count, expires = 0, now + window
        count += 1
        self.local[key] = (count, expires)
        return count
