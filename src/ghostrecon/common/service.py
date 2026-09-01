import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

from ghostrecon.common.config import Settings
from ghostrecon.common.configuration import (
    require_valid_configuration,
    requirements_for,
)
from ghostrecon.common.database import check_database_schema_ready
from ghostrecon.common.logging import configure_logging
from ghostrecon.security.authentication import IdentityMiddleware
from ghostrecon.security.perimeter import SecurityPerimeterMiddleware, security_error
from ghostrecon.security.rate_limit import DistributedRateLimitMiddleware

REQUEST_COUNT = Counter(
    "ghostrecon_http_requests_total",
    "HTTP requests by service, method, path, and status.",
    ["service", "method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "ghostrecon_http_request_duration_seconds",
    "HTTP request latency by service, method, and path.",
    ["service", "method", "path"],
)
DATABASE_CHECK = "database"


def create_base_app(settings: Settings) -> FastAPI:
    require_valid_configuration(settings)
    configure_logging(settings.service_name, settings.log_level)
    app = FastAPI(
        title=f"GhostRecon {settings.service_name}",
        version="0.1.0",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.add_middleware(MetricsMiddleware, service_name=settings.service_name)
    app.add_middleware(DistributedRateLimitMiddleware, settings=settings)
    app.add_middleware(IdentityMiddleware, settings=settings)
    app.add_middleware(
        SecurityPerimeterMiddleware,
        strict=settings.strict_runtime,
        allow_internal_headers=True,
        allowed_origins=settings.allowed_cors_origins,
        trusted_proxy_cidrs=settings.trusted_proxy_cidrs,
        require_tls=settings.strict_runtime and settings.service_name.value == "gateway-service",
    )
    app.state.settings = settings

    @app.get("/healthz", tags=["system"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    @app.get("/readyz", tags=["system"], response_model=None)
    async def readyz(request: Request) -> dict[str, object] | JSONResponse:
        if settings.strict_runtime:
            identity = getattr(request.state, "identity", None)
            if identity is None or identity.calling_service not in {
                "kubernetes-probe",
                "gateway-service",
            }:
                return security_error(
                    status_code=403,
                    code="readiness_denied",
                    message="readiness requires a probe workload",
                    correlation_id=request.state.correlation_id,
                )
        requirements = requirements_for(settings.service_name)
        checks = {item.check_name: {"status": "configured"} for item in requirements}
        if DATABASE_CHECK in checks:
            schema = await check_database_schema_ready(settings)
            if not schema.ready:
                payload: dict[str, object] = {
                    "status": "not_ready",
                    "service": settings.service_name,
                    "profile": settings.profile.value,
                    "checks": {**checks, DATABASE_CHECK: {"status": "failed"}},
                    "reason": schema.reason or "database schema is not ready",
                }
                if schema.missing_tables:
                    payload["missing_tables"] = list(schema.missing_tables)
                return JSONResponse(status_code=503, content=payload)
        if DATABASE_CHECK in checks:
            checks[DATABASE_CHECK] = {"status": "ready"}
        return {
            "status": "ready",
            "service": settings.service_name,
            "profile": settings.profile.value,
            "checks": checks,
        }

    @app.get("/metrics", tags=["system"])
    async def metrics(request: Request) -> Response:
        if settings.strict_runtime:
            identity = getattr(request.state, "identity", None)
            if identity is None or identity.calling_service != "metrics-collector":
                return security_error(
                    status_code=403,
                    code="metrics_denied",
                    message="metrics require the collector workload",
                    correlation_id=request.state.correlation_id,
                )
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, _: ValueError) -> JSONResponse:
        return security_error(
            status_code=400,
            code="invalid_request",
            message="request is invalid",
            correlation_id=getattr(request.state, "correlation_id", "unavailable"),
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        codes = {
            401: "authentication_required",
            403: "permission_denied",
            404: "not_found",
            409: "conflict",
            422: "invalid_request",
            429: "rate_limited",
            503: "security_dependency_unavailable",
        }
        message = exc.detail if isinstance(exc.detail, str) else "request was denied"
        return security_error(
            status_code=exc.status_code,
            code=codes.get(exc.status_code, "request_denied"),
            message=message,
            correlation_id=getattr(request.state, "correlation_id", "unavailable"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, _: RequestValidationError) -> JSONResponse:
        return security_error(
            status_code=422,
            code="invalid_request",
            message="request validation failed",
            correlation_id=getattr(request.state, "correlation_id", "unavailable"),
        )

    return app


class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, service_name: str) -> None:
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        path = request.scope.get("route").path if request.scope.get("route") else request.url.path
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        REQUEST_LATENCY.labels(self.service_name, request.method, path).observe(elapsed)
        REQUEST_COUNT.labels(
            self.service_name, request.method, path, str(response.status_code)
        ).inc()
        return response
