from pathlib import Path

from fastapi.testclient import TestClient

from ghostrecon.common.config import Settings
from ghostrecon.security.operations import OPERATIONS
from ghostrecon.service_apps.factory import build_app
from ghostrecon.service_apps.routers import ROUTERS


def test_every_domain_route_has_a_complete_operation_policy() -> None:
    for router in ROUTERS.values():
        for route in router.routes:
            if not hasattr(route, "methods"):
                continue
            policy = OPERATIONS.require(f"domain.{route.name}")
            assert policy.owner
            assert policy.resource.startswith("/v1/")
            assert policy.test_ids
            assert policy.maximum_body_bytes >= 0


def test_all_auth_and_security_routes_are_classified() -> None:
    from ghostrecon.service_apps.routers.auth import router

    for route in router.routes:
        assert OPERATIONS.require(route.operation_id).owner == "gateway-service"


def test_generated_security_matrices_are_current() -> None:
    import subprocess
    import sys

    subprocess.run(  # noqa: S603
        [sys.executable, "scripts/generate_security_matrices.py", "--check"], check=True
    )


def test_rls_migrations_stage_enable_then_force() -> None:
    enable = Path("migrations/versions/0018_enable_grouped_rls.py").read_text()
    force = Path("migrations/versions/0019_force_grouped_rls.py").read_text()
    assert "ENABLE ROW LEVEL SECURITY" in enable
    assert "FORCE ROW LEVEL SECURITY" in force
    assert "DISABLE ROW LEVEL SECURITY" in enable
    assert "NO FORCE ROW LEVEL SECURITY" in force


def test_local_security_headers_and_legacy_identity_are_hardened() -> None:
    client = TestClient(build_app(Settings(service_name="gateway-service")))
    response = client.get("/healthz", headers={"X-Actor": "administrator"})
    assert response.status_code == 400
    payload = response.json()
    assert set(payload) == {"code", "message", "correlation_id"}

    response = client.get("/healthz")
    assert response.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" not in response.headers


def test_compose_exposes_only_gateway_application_port() -> None:
    compose = Path("docker-compose.yml").read_text()
    assert compose.count("${GHOSTRECON_HTTP_PORT:-8080}:8080") == 1
    assert "${GHOSTRECON_CONSOLE_PORT" not in compose
    assert "${GHOSTRECON_EVENT_SERVICE_PORT" not in compose


def test_chart_has_distinct_workload_identity_and_gateway_ingress() -> None:
    deployment = Path("deploy/helm/ghostrecon/templates/deployment.yaml").read_text()
    workers = Path("deploy/helm/ghostrecon/templates/workers.yaml").read_text()
    ingress = Path("deploy/helm/ghostrecon/templates/ingress.yaml").read_text()
    assert "serviceAccountName: {{ $service }}" in deployment
    assert "ghostrecon-{{ $service }}-identity" in deployment
    assert "serviceAccountName: ghostrecon-worker-{{ $worker.name }}" in workers
    assert "name: gateway-service" in ingress
