from ghostrecon.services.email_candidates import generate_email_candidates


def test_generate_email_candidates_orders_common_patterns_first() -> None:
    candidates = generate_email_candidates("Ada Lovelace", "example.com")

    assert candidates[0].email == "ada.lovelace@example.com"
    assert len({candidate.email for candidate in candidates}) == len(candidates)


def test_generate_email_candidates_requires_first_and_last_name() -> None:
    assert generate_email_candidates("Ada", "example.com") == []
