from fastapi import FastAPI, Request, Response
from redis.asyncio import Redis
from starlette.middleware.wsgi import WSGIMiddleware

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.configuration import require_valid_configuration
from ghostrecon.common.database import get_session_factory
from ghostrecon.common.service import create_base_app
from ghostrecon.security.oidc_client import OIDCClient
from ghostrecon.security.proxy import forward_to_console
from ghostrecon.security.repositories import SecurityRepository
from ghostrecon.security.sessions import SESSION_COOKIE_NAME
from ghostrecon.security.transactions import OIDCTransactionRepository, RedisReplayDetector
from ghostrecon.security.workload import WorkloadSigner, WorkloadVerifier
from ghostrecon.service_apps.routers import ROUTERS


def build_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    require_valid_configuration(resolved)
    app = create_base_app(resolved)
    if resolved.strict_runtime:
        if resolved.service_name.value == "gateway-service":
            app.state.workload_signer = WorkloadSigner(resolved)
            redis = Redis.from_url(str(resolved.redis_url), decode_responses=False)
            app.state.security_redis = redis
            app.state.workload_identity_resolver = WorkloadVerifier(
                resolved, replay_detector=RedisReplayDetector(redis)
            ).resolve
            repository = SecurityRepository(get_session_factory(resolved), resolved)
            app.state.security_repository = repository
            app.state.oidc_client = OIDCClient(resolved)
            app.state.oidc_transactions = OIDCTransactionRepository(
                redis,
                encryption_key=resolved.oidc_transaction_encryption_key or "",
                ttl_seconds=resolved.oidc_transaction_ttl_seconds,
            )

            async def resolve_session(request):
                raw = request.cookies.get(SESSION_COOKIE_NAME)
                if not raw:
                    return None
                return await repository.resolve(raw, correlation_id=request.state.correlation_id)

            async def validate_csrf(request):
                identity = getattr(request.state, "identity", None)
                return identity is not None and repository.verify_csrf(
                    request.headers.get("x-csrf-token"), identity
                )

            app.state.session_identity_resolver = resolve_session
            app.state.csrf_validator = validate_csrf
        elif resolved.service_name.value != "migration-job":
            redis = Redis.from_url(str(resolved.redis_url), decode_responses=False)
            app.state.workload_identity_resolver = WorkloadVerifier(
                resolved, replay_detector=RedisReplayDetector(redis)
            ).resolve
    router = ROUTERS.get(resolved.service_name)
    if router is None:
        known = ", ".join(sorted(ROUTERS))
        raise RuntimeError(f"Unknown GhostRecon service {resolved.service_name!r}. Known: {known}")
    # The console process serves only Dash. Domain handlers stay in owner services.
    if resolved.service_name.value != "console-service":
        app.include_router(router)
    if resolved.service_name.value == "gateway-service":
        from ghostrecon.service_apps.routers.auth import router as auth_router

        app.include_router(auth_router)

        if resolved.strict_runtime:

            @app.api_route(
                "/{console_path:path}",
                methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                include_in_schema=False,
            )
            async def console_proxy(request: Request, console_path: str) -> Response:
                del console_path
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    validator = getattr(request.app.state, "csrf_validator", None)
                    if validator is not None and not await validator(request):
                        from ghostrecon.security.perimeter import security_error

                        return security_error(
                            status_code=403,
                            code="csrf_denied",
                            message="CSRF validation failed",
                            correlation_id=request.state.correlation_id,
                        )
                return await forward_to_console(request, request.state.identity)

    if resolved.service_name == "console-service":
        from ghostrecon.console.app import create_console_dash_app

        dash_app = create_console_dash_app(resolved)
        app.mount("/", WSGIMiddleware(dash_app.server))
    return app
