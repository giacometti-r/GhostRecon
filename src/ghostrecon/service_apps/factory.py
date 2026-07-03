from fastapi import FastAPI

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.service import create_base_app
from ghostrecon.service_apps.routers import ROUTERS


def build_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    app = create_base_app(resolved)
    router = ROUTERS.get(resolved.service_name)
    if router is None:
        known = ", ".join(sorted(ROUTERS))
        raise RuntimeError(f"Unknown GhostRecon service {resolved.service_name!r}. Known: {known}")
    app.include_router(router)
    return app
