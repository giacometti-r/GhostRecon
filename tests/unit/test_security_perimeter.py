from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ghostrecon.security.operations import OPERATIONS, AuthenticationMode, Exposure
from ghostrecon.security.perimeter import SecurityPerimeterMiddleware


def _app(*, strict: bool = True) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityPerimeterMiddleware, strict=strict, maximum_body_bytes=8)

    @app.post("/unsafe")
    async def unsafe() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_strict_perimeter_rejects_legacy_identity_headers() -> None:
    response = TestClient(_app()).post("/unsafe", headers={"X-Actor": "administrator"})
    assert response.status_code == 400
    assert response.json()["code"] == "reserved_identity_header"
    assert response.json()["correlation_id"]


def test_strict_perimeter_rejects_external_obo_headers() -> None:
    response = TestClient(_app()).post("/unsafe", headers={"X-GhostRecon-OBO": "attacker"})
    assert response.status_code == 400
    assert response.json()["code"] == "reserved_internal_header"


def test_perimeter_enforces_body_bound_and_security_headers() -> None:
    too_large = TestClient(_app()).post(
        "/unsafe",
        content=b"123456789",
        headers={"Content-Type": "application/json"},
    )
    assert too_large.status_code == 413
    assert too_large.json()["code"] == "body_too_large"

    response = TestClient(_app()).post(
        "/unsafe", content=b"{}", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert "max-age=31536000" in response.headers["strict-transport-security"]


def test_operation_registry_has_explicit_system_and_security_policies() -> None:
    audit = OPERATIONS.require("security.audit.read")
    assert audit.authentication is AuthenticationMode.HUMAN
    assert audit.rls and audit.audit
    assert OPERATIONS.require("system.docs.read").exposure is Exposure.DISABLED
    assert OPERATIONS.require("system.metrics.read").allowed_callers == frozenset(
        {"metrics-collector"}
    )
