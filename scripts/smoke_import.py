from ghostrecon.models.api import EmailCandidateRequest, ScoreRequest
from ghostrecon.service_apps.runtime import app
from ghostrecon.services.email_candidates import generate_email_candidates
from ghostrecon.services.scoring import score_lead


def main() -> None:
    candidates = generate_email_candidates("Ada Lovelace", "example.com")
    assert candidates
    assert EmailCandidateRequest(full_name="Ada Lovelace", domain="example.com")
    score = score_lead(
        ScoreRequest(
            account={"named_account_flag": True, "employee_count": 500, "industry": "Software"},
            signals=[{"signal_type": "kev", "signal_strength": 25}],
        )
    )
    assert score.composite_score > 0
    assert app.title.startswith("GhostRecon")


if __name__ == "__main__":
    main()
