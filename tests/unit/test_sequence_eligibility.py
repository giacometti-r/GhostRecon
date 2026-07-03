from ghostrecon.models.api import (
    ScoreResult,
    SequenceEligibilityRequest,
    SuppressionCheckResult,
)
from ghostrecon.services.sequencing import evaluate_sequence_eligibility


def test_sequence_requires_approval_for_high_score() -> None:
    result = evaluate_sequence_eligibility(
        SequenceEligibilityRequest(
            contact={"full_name": "Ada Lovelace"},
            score=ScoreResult(
                fit_score=90,
                intent_score=90,
                composite_score=90,
                threshold_met=True,
                reasons=[],
            ),
            suppression=SuppressionCheckResult(allowed=True),
        )
    )

    assert result.eligible is True
    assert result.requires_approval is True
    assert result.next_action == "request_approval"


def test_sequence_blocks_suppressed_contact() -> None:
    result = evaluate_sequence_eligibility(
        SequenceEligibilityRequest(
            contact={"full_name": "Ada Lovelace"},
            score=ScoreResult(
                fit_score=90,
                intent_score=90,
                composite_score=90,
                threshold_met=True,
                reasons=[],
            ),
            suppression=SuppressionCheckResult(allowed=False, reason="opt out"),
        )
    )

    assert result.eligible is False
    assert result.next_action == "suppress"
