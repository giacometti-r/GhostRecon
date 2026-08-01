from __future__ import annotations

import re
import secrets
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

CORRELATION_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
LEGACY_IDENTITY_HEADERS = frozenset(
    {"x-actor", "x-operator-role", "x-user", "x-user-role", "x-user-email"}
)
RESERVED_INTERNAL_HEADERS = frozenset(
    {"x-ghostrecon-obo", "x-ghostrecon-service-authorization"}
)


def security_error(
    *,
    status_code: int,
    code: str,
    message: str,
    correlation_id: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "correlation_id": correlation_id,
        },
    )


class SecurityPerimeterMiddleware(BaseHTTPMiddleware):
    """Transport-level bounds and reserved-header protection.

    Authentication and route policy middleware run after this perimeter.  The
    perimeter deliberately makes no authorization decision from caller headers.
    """

    def __init__(
        self,
        app: object,
        *,
        strict: bool,
        maximum_body_bytes: int = 1024 * 1024,
        maximum_header_bytes: int = 16 * 1024,
        maximum_query_bytes: int = 8 * 1024,
        internal_request: Callable[[Request], Awaitable[bool]] | None = None,
    ) -> None:
        super().__init__(app)
        self.strict = strict
        self.maximum_body_bytes = maximum_body_bytes
        self.maximum_header_bytes = maximum_header_bytes
        self.maximum_query_bytes = maximum_query_bytes
        self.internal_request = internal_request

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get("x-correlation-id", "")
        if not CORRELATION_PATTERN.fullmatch(correlation_id):
            correlation_id = secrets.token_urlsafe(18)
        request.state.correlation_id = correlation_id

        total_header_bytes = sum(
            len(name) + len(value) for name, value in request.scope.get("headers", [])
        )
        if total_header_bytes > self.maximum_header_bytes:
            return security_error(
                status_code=431,
                code="headers_too_large",
                message="request headers exceed the configured limit",
                correlation_id=correlation_id,
            )
        if len(request.scope.get("query_string", b"")) > self.maximum_query_bytes:
            return security_error(
                status_code=414,
                code="query_too_large",
                message="request query exceeds the configured limit",
                correlation_id=correlation_id,
            )
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > self.maximum_body_bytes
            except ValueError:
                too_large = True
            if too_large:
                return security_error(
                    status_code=413,
                    code="body_too_large",
                    message="request body exceeds the configured limit",
                    correlation_id=correlation_id,
                )

        header_names = {name.lower() for name in request.headers}
        if self.strict and header_names & LEGACY_IDENTITY_HEADERS:
            return security_error(
                status_code=400,
                code="reserved_identity_header",
                message="caller identity headers are not accepted",
                correlation_id=correlation_id,
            )
        if self.strict and header_names & RESERVED_INTERNAL_HEADERS:
            trusted = self.internal_request is not None and await self.internal_request(request)
            if not trusted:
                return security_error(
                    status_code=400,
                    code="reserved_internal_header",
                    message="reserved internal headers are not accepted",
                    correlation_id=correlation_id,
                )

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response.headers["X-Frame-Options"] = "DENY"
        if self.strict:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
            if request.url.path != "/healthz":
                response.headers["Cache-Control"] = "no-store"
        return response
