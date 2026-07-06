from types import SimpleNamespace

from ghostrecon.models.api import SuppressionCheckRequest
from ghostrecon.services.governance import evaluate_suppression, review_policy_blockers


def test_blocks_role_based_email() -> None:
    result = evaluate_suppression(SuppressionCheckRequest(email="admin@example.com"))

    assert result.allowed is False
    assert "Role-based" in (result.reason or "")


def test_allows_supported_non_role_email() -> None:
    result = evaluate_suppression(SuppressionCheckRequest(email="ada@example.com"))

    assert result.allowed is True


def test_review_policy_blocks_unknown_reuse_suppression_and_missing_lawful_basis() -> None:
    candidate = SimpleNamespace(
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
        origin_type="event_participant",
        policy_snapshot={
            "participant_reuse_state": "unknown",
            "suppression_allowed": False,
            "retention_state": "active",
        },
    )

    blockers = review_policy_blockers(candidate)

    assert "participant_reuse_unknown" in blockers
    assert "suppression_active" in blockers
    assert "missing_lawful_basis" in blockers


def test_review_policy_allows_current_corroborated_incident() -> None:
    candidate = SimpleNamespace(
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
        origin_type="security_incident",
        policy_snapshot={
            "lawful_basis": "legitimate_interest",
            "retention_state": "active",
            "incident_status": "corroborated",
            "corroboration_method": "analyst_decision",
        },
    )

    assert review_policy_blockers(candidate) == []
