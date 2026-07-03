from ghostrecon.models.api import ScoreRequest
from ghostrecon.services.scoring import score_lead


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
