from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from ghostrecon.common import database as database_module
from ghostrecon.common import service as service_module
from ghostrecon.common.config import Settings
from ghostrecon.common.database import SchemaReadiness, check_database_schema_ready
from ghostrecon.models import db as _db_models  # noqa: F401
from ghostrecon.service_apps.factory import build_app


class FakeConnection:
    def __init__(self, table_names: set[str] | None = None, error: Exception | None = None) -> None:
        self.table_names = table_names or set()
        self.error = error

    async def __aenter__(self) -> "FakeConnection":
        if self.error is not None:
            raise self.error
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _statement: Any) -> list[tuple[str]]:
        return [(name,) for name in self.table_names]


class FakeEngine:
    def __init__(self, table_names: set[str] | None = None, error: Exception | None = None) -> None:
        self.table_names = table_names or set()
        self.error = error

    def connect(self) -> FakeConnection:
        return FakeConnection(self.table_names, self.error)


def _all_expected_tables() -> set[str]:
    return set(database_module.Base.metadata.tables) | {"alembic_version"}


def test_schema_readiness_is_ready_when_public_tables_exist(monkeypatch) -> None:
    monkeypatch.setattr(
        database_module,
        "get_engine",
        lambda _settings=None: FakeEngine(_all_expected_tables()),
    )

    result = _run(check_database_schema_ready(Settings(service_name="gateway-service")))

    assert result.ready is True
    assert result.missing_tables == ()
    assert result.reason is None


def test_schema_readiness_reports_missing_public_tables(monkeypatch) -> None:
    present_tables = _all_expected_tables() - {"alembic_version", "cyber_events"}
    monkeypatch.setattr(
        database_module,
        "get_engine",
        lambda _settings=None: FakeEngine(present_tables),
    )

    result = _run(check_database_schema_ready(Settings(service_name="gateway-service")))

    assert result.ready is False
    assert result.reason == "database schema is not migrated"
    assert "alembic_version" in result.missing_tables
    assert "cyber_events" in result.missing_tables


def test_schema_readiness_reports_database_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        database_module,
        "get_engine",
        lambda _settings=None: FakeEngine(error=RuntimeError("connection refused")),
    )

    result = _run(check_database_schema_ready(Settings(service_name="gateway-service")))

    assert result.ready is False
    assert result.reason == "database schema readiness check failed"
    assert result.error == "connection refused"


def test_schema_gated_services_return_not_ready_when_schema_is_missing(monkeypatch) -> None:
    async def not_ready(_settings=None) -> SchemaReadiness:
        return SchemaReadiness(
            ready=False,
            reason="database schema is not migrated",
            missing_tables=("cyber_events",),
        )

    monkeypatch.setattr(service_module, "check_database_schema_ready", not_ready)

    for service_name in ("gateway-service", "reporting-service", "console-service"):
        client = TestClient(build_app(Settings(service_name=service_name)))
        response = client.get("/readyz")

        assert response.status_code == 503
        assert response.json() == {
            "status": "not_ready",
            "service": service_name,
            "reason": "database schema is not migrated",
            "missing_tables": ["cyber_events"],
        }


def test_non_schema_gated_services_keep_process_readiness(monkeypatch) -> None:
    async def unexpected_check(_settings=None) -> SchemaReadiness:
        raise AssertionError("schema readiness should not be checked")

    monkeypatch.setattr(service_module, "check_database_schema_ready", unexpected_check)

    client = TestClient(build_app(Settings(service_name="enrichment-service")))
    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "enrichment-service"}


def test_compose_runs_migrations_before_demo_services() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "  migrate:" in compose
    assert "alembic upgrade head" in compose
    assert "GHOSTRECON_SERVICE_NAME: migration-job" in compose
    assert compose.count("condition: service_completed_successfully") >= 3

    for service_name in ("gateway-service", "console-service", "worker"):
        service_block = compose.split(f"  {service_name}:", maxsplit=1)[1].split("\n\n", 1)[0]
        assert "migrate:" in service_block
        assert "condition: service_completed_successfully" in service_block


def _run(coroutine):
    import asyncio

    return asyncio.run(coroutine)
