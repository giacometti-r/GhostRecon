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
        policy_snapshot={"lawful_basis": "legitimate_interest"},
        policy_snapshot_hash="policy-hash",
        sla_due_at=now,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _candidate_score() -> SimpleNamespace:
    now = datetime(2026, 7, 6, tzinfo=UTC)
    return SimpleNamespace(
        id="score-1",
        target_type="contact",
        target_id="contact-1",
        origin_type="security_incident",
        origin_id="incident-1",
        config_version="sprint7.v1",
        component_scores={
            "fit": 80,
            "relevance": 80,
            "recency": 100,
            "confidence": 82,
            "evidence": 100,
            "policy_blockers": [],
        },
        composite_score=87,
        route="crm_target_review",
        reasons=["Composite score is ready for CRM-target review"],
        policy_snapshot_hash="policy-hash",
        created_at=now,
    )


def _review_decision(decision: str = "approved") -> SimpleNamespace:
    now = datetime(2026, 7, 6, tzinfo=UTC)
    return SimpleNamespace(
        id=f"decision-{decision}",
        review_candidate_id="review-1",
        target_type="email_candidate",
        target_id="email-candidate-1",
        decision=decision,
        actor="analyst@example.com",
        reason_code=f"{decision}_by_analyst",
        reason="Analyst decision.",
        policy_snapshot_hash="policy-hash",
        created_at=now,
    )


def _crm_target() -> SimpleNamespace:
    now = datetime(2026, 7, 6, tzinfo=UTC)
    return SimpleNamespace(
        id="crm-target-1",
        review_candidate_id="review-1",
        review_decision_id="decision-approved",
        target_type="email_candidate",
        target_id="email-candidate-1",
        origin_type="security_incident",
        origin_id="incident-1",
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
        status="pending_export",
        export_status="not_exported",
        policy_snapshot={},
        approval_snapshot={},
        version=1,
        created_at=now,
        updated_at=now,
    )


def _suppression() -> SimpleNamespace:
    now = datetime(2026, 7, 6, tzinfo=UTC)
    return SimpleNamespace(
        id="suppression-1",
        email="ada@example.com",
        domain="example.com",
        contact_id="contact-1",
        channel="email",
        target_type="contact",
        target_id="contact-1",
        reason="Do not contact request.",
        source="governance",
        active=True,
        expires_at=None,
        policy_snapshot={},
        created_at=now,
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


def test_event_participant_enrich_target_route(monkeypatch) -> None:
    async def fake_enrich(participant_id, request, **kwargs):
        assert participant_id == "participant-1"
        assert request.domain == "example.com"
        assert kwargs["actor"] == "analyst@example.com"
        return {
            "contact_candidate": _contact_candidate().__dict__,
            "email_candidates": [_email_candidate("verified").__dict__],
            "verified_email": "ada.lovelace@example.com",
            "review_reason": None,
        }

    monkeypatch.setattr(routers, "enrich_event_participant_target", fake_enrich)

    client = TestClient(build_app(Settings(service_name="enrichment-service")))
    response = client.post(
        "/v1/enrichment/event-participants/participant-1/enrich-target",
        headers={"Idempotency-Key": "enrich-1", "X-Actor": "analyst@example.com"},
        json={"domain": "example.com", "role_scope": "security"},
    )

    assert response.status_code == 200
    assert response.json()["verified_email"] == "ada.lovelace@example.com"


def test_watch_target_contact_and_domain_discovery_routes(monkeypatch) -> None:
    now = datetime(2026, 7, 6, tzinfo=UTC)

    async def fake_find_contacts(watch_target_id, **kwargs):
        assert watch_target_id == "watch-1"
        assert kwargs["actor"] == "analyst@example.com"
        return {
            "watch_target": {
                "id": "watch-1",
                "target_type": "company",
                "canonical_target_key": "example-corp",
                "display_name": "Example Corp",
                "query_config": {},
                "enabled": True,
                "monitoring_enabled": True,
                "monitoring_status": "completed",
                "owner": "analyst@example.com",
                "created_by": "analyst@example.com",
                "version": 1,
                "created_at": now,
                "updated_at": now,
            },
            "query": (
                'site:linkedin.com/in ("Head of Cybersecurity" OR "CISO" OR '
                '"Chief Information Security Officer" OR "CTO" OR "Chief Technology Officer") '
                '"Example Corp"'
            ),
            "provider": "local_demo",
            "contact_candidates": [_contact_candidate().__dict__],
        }

    async def fake_discover_domain(candidate_id, **kwargs):
        assert candidate_id == "contact-candidate-1"
        assert kwargs["actor"] == "analyst@example.com"
        return {
            "contact_candidate": _contact_candidate().__dict__,
            "query": "Example Corp official website",
            "provider": "local_demo",
            "selected_url": "https://www.example.com/en",
            "discovered_domain": "example.com",
            "status": "eligible",
            "review_reason": None,
        }

    monkeypatch.setattr(routers, "discover_watch_target_contacts", fake_find_contacts)
    monkeypatch.setattr(routers, "discover_contact_candidate_domain", fake_discover_domain)

    client = TestClient(build_app(Settings(service_name="enrichment-service")))
    contacts = client.post(
        "/v1/enrichment/watch-targets/watch-1/find-contact",
        headers={"X-Actor": "analyst@example.com"},
    )
    domain = client.post(
        "/v1/enrichment/contact-candidates/contact-candidate-1/discover-domain",
        headers={"X-Actor": "analyst@example.com"},
    )

    assert contacts.status_code == 200
    assert contacts.json()["provider"] == "local_demo"
    assert "site:linkedin.com/in" in contacts.json()["query"]
    assert domain.json()["discovered_domain"] == "example.com"


def test_review_candidates_route_is_read_only_queue(monkeypatch) -> None:
    async def fake_list_review_candidates(**kwargs):
        return [_review_candidate()]

    monkeypatch.setattr(routers, "list_review_candidates", fake_list_review_candidates)

    client = TestClient(build_app(Settings(service_name="governance-service")))
    payload = client.get("/v1/review/candidates").json()

    assert payload["candidates"][0]["status"] == "open"
    assert payload["candidates"][0]["candidate_type"] == "email_verification"


def test_scoring_candidate_route_persists_versioned_score(monkeypatch) -> None:
    async def fake_create_score(*args, **kwargs):
        return _candidate_score()

    monkeypatch.setattr(routers, "create_candidate_score", fake_create_score)

    client = TestClient(build_app(Settings(service_name="scoring-routing-service")))
    payload = client.post(
        "/v1/scoring/candidates",
        headers={"Idempotency-Key": "idem-score"},
        json={
            "target_type": "contact",
            "target_id": "contact-1",
            "origin_type": "security_incident",
            "origin_id": "incident-1",
            "source_definition_id": "source-1",
            "source_item_ids": ["raw-1"],
            "policy_snapshot": {"lawful_basis": "legitimate_interest"},
        },
    ).json()

    assert payload["config_version"] == "sprint7.v1"
    assert payload["route"] == "crm_target_review"


def test_review_decision_routes_and_crm_targets(monkeypatch) -> None:
    async def fake_approve(*args, **kwargs):
        return _review_decision("approved")

    async def fake_reject(*args, **kwargs):
        return _review_decision("rejected")

    async def fake_bulk(*args, **kwargs):
        return [_review_decision("approved")]

    async def fake_targets(*args, **kwargs):
        return [_crm_target()]

    monkeypatch.setattr(routers, "approve_review_candidate", fake_approve)
    monkeypatch.setattr(routers, "reject_review_candidate", fake_reject)
    monkeypatch.setattr(routers, "bulk_decide_review_candidates", fake_bulk)
    monkeypatch.setattr(routers, "list_crm_targets", fake_targets)

    client = TestClient(build_app(Settings(service_name="governance-service")))
    approved = client.post(
        "/v1/review/candidates/review-1/approve",
        headers={"Idempotency-Key": "idem-approve", "X-Actor": "analyst@example.com"},
        json={"version": 1, "reason_code": "approved_by_analyst"},
    ).json()
    rejected = client.post(
        "/v1/review/candidates/review-1/reject",
        headers={"Idempotency-Key": "idem-reject", "X-Actor": "analyst@example.com"},
        json={"version": 1, "reason_code": "false_positive"},
    ).json()
    bulk = client.post(
        "/v1/review/candidates/bulk-decision",
        headers={"Idempotency-Key": "idem-bulk", "X-Actor": "analyst@example.com"},
        json={
            "candidate_ids": ["review-1"],
            "decision": "approved",
            "candidate_versions": {"review-1": 1},
            "reason_code": "bulk_approved",
        },
    ).json()
    targets = client.get("/v1/review/crm-targets").json()

    assert approved["decision"] == "approved"
    assert rejected["decision"] == "rejected"
    assert bulk["decisions"][0]["decision"] == "approved"
    assert targets["crm_targets"][0]["export_status"] == "not_exported"


def test_suppression_and_incident_governance_routes(monkeypatch) -> None:
    async def fake_create_suppression(*args, **kwargs):
        return _suppression()

    async def fake_corroborate(*args, **kwargs):
        return _review_decision("approved")

    async def fake_reject_incident(*args, **kwargs):
        return _review_decision("rejected")

    async def fake_revert_incident(*args, **kwargs):
        return _review_decision("rejected")

    monkeypatch.setattr(routers, "create_suppression", fake_create_suppression)
    monkeypatch.setattr(routers, "corroborate_incident", fake_corroborate)
    monkeypatch.setattr(routers, "reject_incident", fake_reject_incident)
    monkeypatch.setattr(routers, "revert_incident", fake_revert_incident)

    client = TestClient(build_app(Settings(service_name="gateway-service")))
    suppression = client.post(
        "/v1/suppressions",
        headers={"Idempotency-Key": "idem-suppression"},
        json={"email": "ada@example.com", "reason": "Do not contact request."},
    ).json()
    corroborated = client.post(
        "/v1/governance/incidents/incident-1/corroborate",
        headers={"Idempotency-Key": "idem-corroborate"},
        json={
            "version": 1,
            "method": "analyst_decision",
            "reason_code": "analyst_verified",
        },
    ).json()
    rejected = client.post(
        "/v1/governance/incidents/incident-1/reject",
        headers={"Idempotency-Key": "idem-reject-incident"},
        json={"version": 1, "reason_code": "false_positive"},
    ).json()
    reverted = client.post(
        "/v1/governance/incidents/incident-1/revert",
        headers={"Idempotency-Key": "idem-revert-incident"},
        json={"version": 2, "reason_code": "analyst_reverted"},
    ).json()

    assert suppression["id"] == "suppression-1"
    assert corroborated["decision"] == "approved"
    assert rejected["decision"] == "rejected"
    assert reverted["decision"] == "rejected"
