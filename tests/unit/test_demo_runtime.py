from pathlib import Path
from uuid import UUID

import pytest

from ghostrecon.common.config import Settings
from ghostrecon.demo_seed import (
    DEMO_SEED_IDS,
    DEMO_SEED_REPORTING_RESOURCES,
    DemoSeedSafetyError,
    assert_demo_seed_allowed,
)


def test_demo_seed_ids_are_stable_uuid_strings() -> None:
    ids = DEMO_SEED_IDS.__dict__

    assert set(ids) == {
        "source_definition_id",
        "cyber_event_id",
        "security_incident_id",
        "watch_target_id",
        "review_candidate_id",
        "crm_target_id",
    }
    assert all(str(UUID(value)) == value for value in ids.values())
    assert len(set(ids.values())) == len(ids)


def test_demo_seed_refuses_non_local_environments_by_default(monkeypatch) -> None:
    monkeypatch.delenv("GHOSTRECON_ALLOW_DEMO_SEED", raising=False)

    with pytest.raises(DemoSeedSafetyError):
        assert_demo_seed_allowed(Settings(environment="prod"))


def test_demo_seed_allows_explicit_non_local_override(monkeypatch) -> None:
    monkeypatch.setenv("GHOSTRECON_ALLOW_DEMO_SEED", "1")

    assert_demo_seed_allowed(Settings(environment="prod"))


def test_demo_seed_covers_demo_check_reporting_resources() -> None:
    assert DEMO_SEED_REPORTING_RESOURCES == (
        "source_definitions",
        "cyber_events",
        "security_incidents",
        "watch_targets",
        "review_candidates",
        "crm_targets",
    )


def test_makefile_exposes_demo_workflow_targets() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "demo-reset:" in makefile
    assert "demo-check:" in makefile
    assert "demo: demo-reset" in makefile
    assert "sh scripts/demo_check.sh" in makefile


def test_demo_check_script_covers_required_health_checks() -> None:
    script = Path("scripts/demo_check.sh").read_text(encoding="utf-8")

    for service in (
        "postgres",
        "redis",
        "gateway-service",
        "console-service",
        "worker",
        "email-verifier",
    ):
        assert service in script

    for table_name in DEMO_SEED_REPORTING_RESOURCES:
        assert table_name in script

    for endpoint in (
        "/healthz",
        "/readyz",
        "/v1/reporting/kpis/catalog",
        "/v1/reporting/events",
        "/v1/reporting/incidents",
        "/v1/reporting/watch-targets",
        "/v1/reporting/review-queue",
        "/v1/reporting/crm-targets",
        "/v1/reporting/source-health",
        "/_dash-dependencies",
    ):
        assert endpoint in script

    assert "redis-cli ping" in script
    assert "alembic_version" in script
