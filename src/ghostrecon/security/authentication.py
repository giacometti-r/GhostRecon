from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ghostrecon.common.config import Settings

from .identity import AssuranceLevel, IdentityContext, IdentityType
from .perimeter import security_error
from .policy import Role, permissions_for_roles


class IdentityMiddleware(BaseHTTPMiddleware):
    """Resolve identity once at the edge; handlers never inspect identity headers."""

    def __init__(self, app: object, *, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        public_path = request.url.path in {
            "/healthz",
            "/auth/login",
            "/auth/callback",
            "/auth/provider-logout/callback",
        }
        has_workload_token = bool(request.headers.get("x-ghostrecon-service-authorization"))
        if public_path and not has_workload_token:
            return await call_next(request)
        if (
            self.settings.authentication_backend == "local_oidc"
            and not self.settings.strict_runtime
        ):
            request.state.identity = self._local_identity(request)
            return await call_next(request)
        if self.settings.service_name.value != "gateway-service" or has_workload_token:
            resolver = getattr(request.app.state, "workload_identity_resolver", None)
        else:
            resolver = getattr(request.app.state, "session_identity_resolver", None)
        if resolver is None:
            return security_error(
                status_code=503,
                code="authentication_unavailable",
                message="authentication is temporarily unavailable",
                correlation_id=request.state.correlation_id,
            )
        try:
            identity = await resolver(request)
        except ValueError:
            return security_error(
                status_code=401,
                code="invalid_authentication",
                message="authentication is invalid",
                correlation_id=request.state.correlation_id,
            )
        if identity is None:
            return security_error(
                status_code=401,
                code="authentication_required",
                message="authentication is required",
                correlation_id=request.state.correlation_id,
            )
        request.state.identity = identity
        return await call_next(request)

    def _local_identity(self, request: Request) -> IdentityContext:
        roles = frozenset({Role.ADMINISTRATOR.value})
        correlation_id = getattr(request.state, "correlation_id", secrets.token_urlsafe(18))
        return IdentityContext(
            identity_type=IdentityType.HUMAN,
            subject="local-development-user",
            actor_label="Local development administrator",
            issuer="urn:ghostrecon:local-oidc",
            audience=("ghostrecon-gateway",),
            roles=roles,
            permissions=permissions_for_roles(roles),
            calling_service=None,
            on_behalf_of_subject=None,
            authentication_method="local_oidc",
            authenticated_at=datetime.now(UTC),
            assurance=AssuranceLevel.PHISHING_RESISTANT,
            session_id=UUID("00000000-0000-0000-0000-000000000001"),
            correlation_id=correlation_id,
            request_id=secrets.token_urlsafe(12),
            claim_mapping_version="local.v1",
            permission_policy_version="sprint25b.v1",
            environment=self.settings.profile.value,
            email_verified=True,
        )
