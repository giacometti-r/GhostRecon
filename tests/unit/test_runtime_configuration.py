from __future__ import annotations

import os

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ghostrecon.common.config import (
    SERVICE_REQUIREMENTS,
    ConfigurationValidationError,
    RuntimeProfile,
    ServiceName,
    Settings,
    validate_configuration,
)
from ghostrecon.common.preflight import run as run_preflight
from ghostrecon.common.synthetic_guard import (
    PROHIBITED_SYNTHETIC_MARKERS,
    SyntheticPersistenceError,
    enable_synthetic_persistence_guard,
)
from ghostrecon.models.db import CrmExportBatch
from ghostrecon.services.search_adapters import search_provider_for_settings


def _strict_security(service: str) -> dict[str, object]:
    return {
        "authentication_backend": "oidc",
        "service_identity": service,
        "service_private_key_path": "/run/secrets/service-key.pem",
        "service_private_key_id": "key-1",
        "service_trust_bundle_path": "/run/secrets/trust.json",
        "audit_hmac_key": "a" * 32,
        "docs_enabled": False,
    }


def test_runtime_profiles_and_services_are_published() -> None:
    assert {item.value for item in RuntimeProfile} == {
        "local",
        "test",
        "staging",
        "production",
    }
    assert set(SERVICE_REQUIREMENTS) == set(ServiceName)


@pytest.mark.parametrize("profile", ["dev", "prod", "preview", ""])
def test_unknown_or_retired_profiles_are_rejected(profile: str) -> None:
    with pytest.raises(ValidationError):
        Settings(profile=profile)


def test_retired_environment_setting_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="prod")


def test_database_only_service_does_not_own_provider_credentials() -> None:
    settings = Settings(
        profile="production",
        service_name="reporting-service",
        database_url="postgresql+asyncpg://reporter:strong-password@db.internal/ghostrecon",
        **_strict_security("reporting-service"),
    )
    assert validate_configuration(settings) == ()


def test_crm_validation_is_scoped_to_attio_credentials() -> None:
    settings = Settings(
        profile="staging",
        service_name="crm-service",
        database_url="postgresql+asyncpg://crm:strong-password@db.internal/ghostrecon",
        crm_provider="attio",
        **_strict_security("crm-service"),
    )
    issues = validate_configuration(settings)
    assert {(item.setting_name, item.error_code) for item in issues} == {
        ("attio_access_token", "missing_credential")
    }


def test_configuration_errors_and_settings_repr_do_not_expose_secrets() -> None:
    secret = "super" + "-secret-token"
    settings = Settings(
        profile="production",
        service_name="crm-service",
        database_url="postgresql+asyncpg://crm:password@db.internal/ghostrecon",
        crm_provider="attio",
        attio_access_token=secret,
    )
    rendered = repr(settings)
    issues = validate_configuration(settings)

    assert secret not in rendered
    assert "password" not in rendered
    assert all(secret not in repr(issue) for issue in issues)


@pytest.mark.parametrize(
    ("service_name", "overrides", "setting_name", "error_code"),
    [
        (
            "event-intelligence-service",
            {
                "geocoder_provider": "nominatim",
                "nominatim_base_url": "http://geocoder.company.ch",
                "nominatim_user_agent": "GhostRecon (mailto:ops@company.ch)",
            },
            "nominatim_base_url",
            "insecure_public_url",
        ),
        (
            "enrichment-service",
            {
                "search_provider": "openserp",
                "openserp_base_url": "http://search.company.ch",
                "crawl_user_agent": "GhostRecon (mailto:ops@company.ch)",
            },
            "openserp_base_url",
            "unsafe_url",
        ),
        (
            "console-service",
            {"gateway_base_url": "https://operator:credential@gateway.company.ch"},
            "gateway_base_url",
            "credential_bearing_url",
        ),
    ],
)
def test_strict_urls_reject_public_http_and_embedded_credentials(
    service_name: str,
    overrides: dict[str, str],
    setting_name: str,
    error_code: str,
) -> None:
    settings = Settings(
        profile="production",
        service_name=service_name,
        database_url="postgresql+asyncpg://service:strong-password@db.internal/ghostrecon",
        **overrides,
    )
    issues = validate_configuration(settings)
    assert (setting_name, error_code) in {(item.setting_name, item.error_code) for item in issues}
    assert "credential" not in repr(settings)


def test_strict_factory_rejects_synthetic_provider() -> None:
    settings = Settings(profile="staging", search_provider="local_demo")
    with pytest.raises(ConfigurationValidationError) as exc_info:
        search_provider_for_settings(settings)
    assert exc_info.value.issues[0].error_code == "synthetic_adapter"


@pytest.mark.parametrize("marker", sorted(PROHIBITED_SYNTHETIC_MARKERS))
def test_strict_session_rejects_exact_synthetic_provider_markers(marker: str) -> None:
    session = Session()
    enable_synthetic_persistence_guard(session, RuntimeProfile.PRODUCTION)
    session.add(
        CrmExportBatch(
            provider=marker,
            requested_by="operator",
            status="pending",
            crm_target_ids=[],
            selection_hash="hash",
            idempotency_key=f"batch:{marker}",
            counts={},
            reconciliation_summary={},
        )
    )
    with pytest.raises(SyntheticPersistenceError):
        session.flush()


def test_preflight_rejects_retired_environment_without_echoing_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in tuple(os.environ):
        if name.startswith("GHOSTRECON_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("GHOSTRECON_ENVIRONMENT", "prod")

    assert run_preflight(["--format", "json"]) == 2
    stdout = capsys.readouterr().out
    assert '"setting_name": "environment"' in stdout
    assert "prod" not in stdout
