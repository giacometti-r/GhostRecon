import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

from ghostrecon.common.config import Settings
from ghostrecon.common.database import check_database_schema_ready
from ghostrecon.common.logging import configure_logging

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
SCHEMA_READY_SERVICES = {"gateway-service", "reporting-service", "console-service"}


def create_base_app(settings: Settings) -> FastAPI:
    configure_logging(settings.service_name, settings.log_level)
    app = FastAPI(
        title=f"GhostRecon {settings.service_name}",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(MetricsMiddleware, service_name=settings.service_name)

    @app.get("/healthz", tags=["system"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    @app.get("/readyz", tags=["system"], response_model=None)
    async def readyz() -> dict[str, str] | JSONResponse:
        if settings.service_name in SCHEMA_READY_SERVICES:
            schema = await check_database_schema_ready(settings)
            if not schema.ready:
                payload: dict[str, object] = {
                    "status": "not_ready",
                    "service": settings.service_name,
                    "reason": schema.reason or "database schema is not ready",
                }
                if schema.missing_tables:
                    payload["missing_tables"] = list(schema.missing_tables)
                if schema.error:
                    payload["error"] = schema.error
                return JSONResponse(status_code=503, content=payload)
        return {"status": "ready", "service": settings.service_name}

    @app.get("/metrics", tags=["system"])
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

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
