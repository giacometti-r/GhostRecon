from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from .context import current_identity, current_operation
from .identity import AssuranceLevel, IdentityContext
from .operations import (
    OPERATIONS,
    AuthenticationMode,
    OperationPolicy,
    classify_domain_operation,
)
from .perimeter import security_error
from .policy import authorize
from .proxy import forward_to_owner


class SecurityRoute(APIRoute):
    """Fail closed for any route that does not have a complete policy."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()
        operation_id = self.operation_id or f"domain.{self.name}"
        OPERATIONS.ensure(
            classify_domain_operation(self.name, self.path, frozenset(self.methods or set()))
        )

        async def secured(request: Request) -> Response:
            try:
                policy = OPERATIONS.require(operation_id)
            except KeyError:
                return security_error(
                    status_code=500,
                    code="unclassified_operation",
                    message="operation policy is unavailable",
                    correlation_id=getattr(request.state, "correlation_id", "unavailable"),
                )
            request.state.operation_policy = policy
            if policy.authentication is AuthenticationMode.PUBLIC:
                return await original(request)
            identity: IdentityContext | None = getattr(request.state, "identity", None)
            if identity is None:
                return security_error(
                    status_code=401,
                    code="authentication_required",
                    message="authentication is required",
                    correlation_id=request.state.correlation_id,
                )
            if identity.calling_service is not None:
                if identity.calling_service not in policy.allowed_callers:
                    return security_error(
                        status_code=403,
                        code="caller_not_allowed",
                        message="calling workload is not permitted",
                        correlation_id=request.state.correlation_id,
                    )
                obo_operation = identity.attributes.get("obo_operation")
                if obo_operation is not None and obo_operation != policy.operation_id:
                    return security_error(
                        status_code=403,
                        code="operation_binding_denied",
                        message="represented operation is not permitted",
                        correlation_id=request.state.correlation_id,
                    )
            if policy.permission is not None:
                decision = authorize(
                    identity,
                    policy.permission,
                    minimum_assurance=policy.assurance or AssuranceLevel.EMAIL_OTP,
                    maximum_authentication_age_seconds=(policy.maximum_authentication_age_seconds),
                )
                if not decision.allowed:
                    return security_error(
                        status_code=403,
                        code=decision.code,
                        message="operation is not permitted",
                        correlation_id=request.state.correlation_id,
                    )
            settings = request.app.state.settings
            if (
                settings.strict_runtime
                and settings.service_name.value == "gateway-service"
                and policy.owner != "gateway-service"
            ):
                return await forward_to_owner(request, policy, identity)
            if (
                policy.csrf
                and identity.calling_service is None
                and request.method not in {"GET", "HEAD", "OPTIONS"}
            ):
                csrf_validator = getattr(request.app.state, "csrf_validator", None)
                if csrf_validator is not None and not await csrf_validator(request):
                    return security_error(
                        status_code=403,
                        code="csrf_denied",
                        message="CSRF validation failed",
                        correlation_id=request.state.correlation_id,
                    )
            identity_token = current_identity.set(identity)
            operation_token = current_operation.set(policy.operation_id)
            try:
                response = await original(request)
            finally:
                current_operation.reset(operation_token)
                current_identity.reset(identity_token)
            if isinstance(response, JSONResponse):
                response.headers["Cache-Control"] = "no-store"
            return response

        return secured


def operation_dependency(request: Request) -> OperationPolicy:
    return request.state.operation_policy
