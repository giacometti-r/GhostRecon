from ghostrecon.models.api import CandidateScoreRequest, ScoreRequest
from ghostrecon.services.scoring import SCORING_CONFIG_VERSION, score_candidate_preview, score_lead


def test_score_lead_routes_strong_named_account() -> None:
    result = score_lead(
        ScoreRequest(
            account={
                "named_account_flag": True,
                "employee_count": 500,
                "industry": "Technology",
                "tech_stack": {"cloud": "aws"},
            },
            signals=[{"signal_type": "kev", "signal_strength": 25}],
        )
    )

    assert result.threshold_met is True
    assert result.composite_score >= 60
    assert "Named account" in result.reasons


def test_score_lead_parks_low_context_account() -> None:
    result = score_lead(ScoreRequest(account={}, signals=[]))

    assert result.threshold_met is False
    assert result.composite_score == 0


def test_candidate_score_uses_sprint7_config_and_routes_crm_target_review() -> None:
    result = score_candidate_preview(
        CandidateScoreRequest(
            target_type="contact",
            target_id="contact-1",
            origin_type="security_incident",
            origin_id="incident-1",
            account={
                "named_account_flag": True,
                "employee_count": 500,
                "industry": "Technology",
            },
            contact={"role_scope": "security", "source_confidence": 80},
            signals=[{"signal_type": "kev", "signal_strength": 25}],
            evidence={
                "authoritative": True,
                "independent_source_count": 2,
                "confidence": 82,
                "evidence_freshness_days": 3,
                "attack_vector": "ransomware",
            },
            source_definition_id="source-1",
            source_item_ids=["raw-1"],
            policy_snapshot={
                "lawful_basis": "legitimate_interest",
                "incident_status": "corroborated",
                "corroboration_method": "authoritative_disclosure",
                "retention_state": "active",
            },
        )
    )

    assert result.config_version == SCORING_CONFIG_VERSION
    assert result.route == "crm_target_review"
    assert result.composite_score >= 70
    assert result.policy_blockers == []


def test_candidate_score_fails_closed_for_policy_blockers() -> None:
    result = score_candidate_preview(
        CandidateScoreRequest(
            target_type="contact",
            target_id="contact-1",
            origin_type="event_participant",
            origin_id="participant-1",
            account={"named_account_flag": True, "employee_count": 1000},
            policy_snapshot={"participant_reuse_state": "unknown"},
        )
    )

    assert result.route == "rejected"
    assert "missing_source_lineage" in result.policy_blockers
    assert "participant_reuse_unknown" in result.policy_blockers
    assert "missing_lawful_basis" in result.policy_blockers


def test_candidate_score_treats_missing_numeric_fields_as_zero() -> None:
    result = score_candidate_preview(
        CandidateScoreRequest(
            target_type="contact",
            target_id="contact-1",
            origin_type="security_incident",
            origin_id="incident-1",
            account={"employee_count": None, "source_confidence": None},
            contact={"source_confidence": None},
            signals=[{"signal_type": "kev", "signal_strength": None}],
            evidence={
                "confidence": None,
                "independent_source_count": None,
                "evidence_freshness_days": None,
            },
        )
    )

    assert result.fit_score == 0
    assert result.relevance_score == 35
    assert result.confidence_score == 0
    assert result.evidence_score == 0
    assert result.route == "rejected"
