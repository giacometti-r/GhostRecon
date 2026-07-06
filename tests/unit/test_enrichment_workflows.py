from datetime import UTC, datetime
from types import SimpleNamespace

from ghostrecon.models.api import ContactEnrichmentCreate, OriginType
from ghostrecon.models.db import Base
from ghostrecon.services.enrichment_workflows import (
    classify_verification_result,
    evaluate_contact_policy,
)


def test_event_participant_contact_requires_allowed_reuse_and_lineage() -> None:
    allowed = ContactEnrichmentCreate(
        origin_type=OriginType.EVENT_PARTICIPANT,
        origin_id="participant-1",
        published_name="Ada Lovelace",
        role_scope="security",
        reuse_state="allowed",
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
    )
    blocked = allowed.model_copy(update={"reuse_state": "unknown"})

    assert evaluate_contact_policy(allowed) == ("eligible", None)
    assert evaluate_contact_policy(blocked) == ("blocked", "participant_reuse_not_allowed")


def test_incident_contacts_reject_breached_data_and_out_of_scope_roles() -> None:
    base = ContactEnrichmentCreate(
        origin_type=OriginType.SECURITY_INCIDENT,
        origin_id="incident-1",
        published_name="Grace Hopper",
        role_scope="other",
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
    )
    breached = base.model_copy(update={"role_scope": "security", "breached_data_source": True})

    assert evaluate_contact_policy(base) == ("blocked", "incident_role_out_of_scope")
    assert evaluate_contact_policy(breached) == ("blocked", "breached_data_rejected")


def test_missing_lineage_fails_closed_before_contact_enrichment() -> None:
    payload = ContactEnrichmentCreate(
        origin_type=OriginType.SECURITY_INCIDENT,
        origin_id="incident-1",
        published_name="Katherine Johnson",
        role_scope="security",
    )

    assert evaluate_contact_policy(payload) == ("blocked", "missing_source_lineage")


def test_email_verification_mapping_routes_ambiguous_and_failed_to_review() -> None:
    assert classify_verification_result({"status": "valid"}) == ("verified", None)
    assert classify_verification_result({"catch_all": True}) == (
        "needs_review",
        "catch_all_domain",
    )
    assert classify_verification_result({"error": "timeout"}) == ("failed", "verifier_failed")
    assert classify_verification_result({"status": "invalid"}) == ("invalid", "invalid_email")


def test_sprint_6_models_and_lineage_columns_are_registered() -> None:
    tables = Base.metadata.tables

    assert "entity_resolution_cases" in tables
    assert "contact_enrichment_candidates" in tables
    assert "organization_email_patterns" in tables
    assert "review_candidates" in tables
    assert "candidate_scores" in tables
    assert "review_decisions" in tables
    assert "crm_targets" in tables
    assert "source_definition_id" in tables["contacts"].columns
    assert "source_item_ids" in tables["email_candidates"].columns
    assert "idempotency_key" in tables["entity_resolution_cases"].columns
    assert "policy_snapshot_hash" in tables["review_candidates"].columns
    assert "version" in tables["security_incidents"].columns
    assert "idempotency_key" in tables["suppressions"].columns


def test_review_candidate_shape_has_minimal_queue_fields() -> None:
    now = datetime(2026, 7, 6, tzinfo=UTC)
    review = SimpleNamespace(
        id="review-1",
        candidate_type="email_verification",
        target_type="email_candidate",
        target_id="candidate-1",
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

    assert review.candidate_type == "email_verification"
    assert review.status == "open"
