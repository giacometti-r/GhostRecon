from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from ghostrecon.common.config import Settings
from ghostrecon.service_apps import routers
from ghostrecon.service_apps.factory import build_app


def _resolution_case(status: str = "resolved") -> SimpleNamespace:
    now = datetime(2026, 7, 6, tzinfo=UTC)
    return SimpleNamespace(
        id="resolution-1",
        origin_type="security_incident",
        origin_id="incident-1",
        entity_kind="organization",
        input_name="Example Corp",
        input_domain="example.com",
        resolved_account_id="account-1" if status == "resolved" else None,
        resolved_name="Example Corp" if status == "resolved" else None,
        resolved_domain="example.com" if status == "resolved" else None,
        status=status,
        confidence=100 if status == "resolved" else 60,
        alternatives=[],
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
        policy_snapshot={},
        review_reason=None if status == "resolved" else "multiple_account_matches",
        version=1,
        created_at=now,
        updated_at=now,
    )


def _contact_candidate(status: str = "eligible") -> SimpleNamespace:
    now = datetime(2026, 7, 6, tzinfo=UTC)
    return SimpleNamespace(
        id="contact-candidate-1",
        entity_resolution_case_id="resolution-1",
        account_id="account-1",
        contact_id="contact-1" if status == "eligible" else None,
        origin_type="security_incident",
        origin_id="incident-1",
        published_name="Ada Lovelace",
        organization="Example Corp",
        title="CISO",
        role_scope="security",
        domain="example.com",
        profile_url=None,
        source_url="https://example.com/security",
        status=status,
        eligibility_reason=None if status == "eligible" else "incident_role_out_of_scope",
        reuse_state="unknown",
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
        policy_snapshot={},
        candidate_payload={},
        review_reason=None if status == "eligible" else "incident_role_out_of_scope",
        version=1,
        created_at=now,
        updated_at=now,
    )


def _email_candidate(status: str = "pending") -> SimpleNamespace:
    now = datetime(2026, 7, 6, tzinfo=UTC)
    return SimpleNamespace(
        id="email-candidate-1",
        contact_id="contact-1",
        email="ada.lovelace@example.com",
        pattern="{first}{sep}{last}",
        confidence=78,
        verification_status=status,
        verification_payload={},
        verification_checked_at=now if status != "pending" else None,
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
        origin_type="security_incident",
        origin_id="incident-1",
        policy_snapshot={},
        review_status="not_required" if status == "verified" else "needs_review",
        review_reason=None if status == "verified" else "catch_all_domain",
        version=2 if status != "pending" else 1,
        created_at=now,
    )


def _review_candidate() -> SimpleNamespace:
    now = datetime(2026, 7, 6, tzinfo=UTC)
    return SimpleNamespace(
        id="review-1",
        candidate_type="email_verification",
        target_type="email_candidate",
        target_id="email-candidate-1",
        origin_type="security_incident",
        origin_id="incident-1",
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
        status="open",
        reason_code="catch_all_domain",
        reason="Email verification result requires analyst review.",
        evidence_summary={},
        policy_snapshot={},
        version=1,
        created_at=now,
        updated_at=now,
    )


def test_enrichment_routes_create_and_list_resolution_and_contacts(monkeypatch) -> None:
    async def fake_create_resolution(*args, **kwargs):
        return _resolution_case()

    async def fake_list_resolutions(**kwargs):
        return [_resolution_case()]

    async def fake_create_contact(*args, **kwargs):
        return _contact_candidate()

    async def fake_list_contacts(**kwargs):
        return [_contact_candidate()]

    monkeypatch.setattr(routers, "create_entity_resolution", fake_create_resolution)
    monkeypatch.setattr(routers, "list_entity_resolutions", fake_list_resolutions)
    monkeypatch.setattr(routers, "create_contact_enrichment_candidate", fake_create_contact)
    monkeypatch.setattr(routers, "list_contact_enrichment_candidates", fake_list_contacts)

    client = TestClient(build_app(Settings(service_name="enrichment-service")))
    resolution = client.post(
        "/v1/enrichment/entity-resolutions",
        headers={"Idempotency-Key": "idem-resolution"},
        json={
            "origin_type": "security_incident",
            "origin_id": "incident-1",
            "organization_name": "Example Corp",
            "domain": "example.com",
            "source_definition_id": "source-1",
            "source_item_ids": ["raw-1"],
        },
    )
    contacts = client.get("/v1/enrichment/contact-candidates").json()["candidates"]

    assert resolution.status_code == 200
    assert resolution.json()["status"] == "resolved"
    assert contacts[0]["contact_id"] == "contact-1"


def test_email_routes_persist_and_verify_candidates(monkeypatch) -> None:
    async def fake_persist(*args, **kwargs):
        return [_email_candidate()]

    async def fake_verify(*args, **kwargs):
        return [_email_candidate("verified")]

    monkeypatch.setattr(routers, "persist_email_candidates", fake_persist)
    monkeypatch.setattr(routers, "verify_email_candidates", fake_verify)

    client = TestClient(build_app(Settings(service_name="email-intelligence-service")))
    persisted = client.post(
        "/v1/email/candidates/persist",
        headers={"Idempotency-Key": "idem-email"},
        json={
            "contact_id": "contact-1",
            "full_name": "Ada Lovelace",
            "domain": "example.com",
            "origin_type": "security_incident",
            "origin_id": "incident-1",
            "source_definition_id": "source-1",
            "source_item_ids": ["raw-1"],
        },
    ).json()
    verified = client.post(
        "/v1/email/verify-batch",
        json={"candidate_ids": ["email-candidate-1"]},
    ).json()

    assert persisted["candidates"][0]["verification_status"] == "pending"
    assert verified["candidates"][0]["verification_status"] == "verified"


def test_review_candidates_route_is_read_only_queue(monkeypatch) -> None:
    async def fake_list_review_candidates(**kwargs):
        return [_review_candidate()]

    monkeypatch.setattr(routers, "list_review_candidates", fake_list_review_candidates)

    client = TestClient(build_app(Settings(service_name="governance-service")))
    payload = client.get("/v1/review/candidates").json()

    assert payload["candidates"][0]["status"] == "open"
    assert payload["candidates"][0]["candidate_type"] == "email_verification"
