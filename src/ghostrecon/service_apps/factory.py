from fastapi import FastAPI
from starlette.middleware.wsgi import WSGIMiddleware

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.configuration import require_valid_configuration
from ghostrecon.common.service import create_base_app
from ghostrecon.service_apps.routers import ROUTERS


def build_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    require_valid_configuration(resolved)
    app = create_base_app(resolved)
    router = ROUTERS.get(resolved.service_name)
    if router is None:
        known = ", ".join(sorted(ROUTERS))
        raise RuntimeError(f"Unknown GhostRecon service {resolved.service_name!r}. Known: {known}")
    app.include_router(router)
    if resolved.service_name == "console-service":
        from ghostrecon.console.app import create_console_dash_app

        dash_app = create_console_dash_app(resolved)
        app.mount("/", WSGIMiddleware(dash_app.server))
    return app
