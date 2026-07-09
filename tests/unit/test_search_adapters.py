from ghostrecon.services.search_adapters import (
    is_suspicious_domain,
    linkedin_contact_query,
    official_website_query,
    registrable_domain_from_url,
    watch_monitoring_queries,
)


def test_linkedin_contact_query_uses_required_google_dork() -> None:
    query = linkedin_contact_query("Example Industries")

    assert query == (
        'site:linkedin.com/in ("Head of Cybersecurity" OR "CISO" OR '
        '"Chief Information Security Officer" OR "CTO" OR "Chief Technology Officer") '
        '"Example Industries"'
    )


def test_official_website_query_and_domain_normalization() -> None:
    assert official_website_query("Apple") == "Apple official website"
    assert registrable_domain_from_url("https://www.apple.com/en") == "apple.com"
    assert registrable_domain_from_url("www.example.co.uk/path") == "example.co.uk"
    assert registrable_domain_from_url("http://security.example.com") == "example.com"


def test_domain_suspicion_and_monitoring_queries_cover_required_categories() -> None:
    assert is_suspicious_domain("linkedin.com") is True
    assert is_suspicious_domain("example.com") is False

    queries = watch_monitoring_queries("Example Industries")
    joined = "\n".join(queries)

    assert "board of directors" in joined
    assert "CISO" in joined
    assert "CTO" in joined
    assert "CIO" in joined
    assert "Head of Cybersecurity" in joined
    assert "cyberattack" in joined
