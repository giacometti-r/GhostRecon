from datetime import UTC, datetime
from types import SimpleNamespace

from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.services.incident_intelligence import (
    article_candidate_from_raw_item,
    incident_candidate_from_article,
)


def _source(**overrides):
    values = {
        "id": "source-1",
        "name": "GDELT cyber incident discovery",
        "query_scope": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _raw(**overrides):
    values = {
        "id": "raw-1",
        "canonical_url": "https://news.example/breach?utm_source=x",
        "content_hash": "hash-1",
        "published_at": datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        "retrieved_at": datetime(2026, 7, 3, 12, 5, tzinfo=UTC),
        "original_language": "English",
        "permitted_excerpt": "Example Corp reports ransomware incident affecting customer systems.",
        "raw_metadata": {
            "gdelt_article": {
                "title": "Example Corp reports ransomware incident",
                "domain": "news.example",
                "sourcecountry": "US",
            }
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_article_candidate_preserves_metadata_and_dedupe_without_full_body() -> None:
    article = article_candidate_from_raw_item(_source(), _raw())

    assert article.canonical_url == "https://news.example/breach"
    assert article.publisher == "news.example"
    assert article.title == "Example Corp reports ransomware incident"
    assert article.original_language == "English"
    assert article.dedupe_key.startswith("news-article:")


def test_incident_candidate_starts_as_company_linked_candidate_case() -> None:
    raw = _raw()
    article = article_candidate_from_raw_item(_source(), raw)
    incident = incident_candidate_from_article(_source(), raw, article)

    assert incident is not None
    assert incident.affected_companies == ["Example Corp"]
    assert incident.attack_vector == "ransomware"
    assert incident.confidence == 75
    assert incident.evidence_family_key == "news-example"


def test_authoritative_source_marks_candidate_authoritative_input() -> None:
    raw = _raw(raw_metadata={"affected_companies": ["Example Corp"], "authoritative": True})
    article = article_candidate_from_raw_item(_source(query_scope={"authoritative": True}), raw)
    incident = incident_candidate_from_article(
        _source(query_scope={"authoritative": True}), raw, article
    )

    assert incident is not None
    assert incident.authoritative is True


def test_incident_event_contracts_keep_lineage() -> None:
    event = new_event(
        event_name=EventName.SECURITY_INCIDENT_DETECTED,
        aggregate_type="security_incident",
        aggregate_id="incident-1",
        source_service="incident-intelligence-service",
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
        payload={"security_incident_id": "incident-1", "status": "candidate"},
    )

    payload = event.model_dump(mode="json")

    assert payload["event_name"] == "security_incident.detected"
    assert payload["producer"] == "incident-intelligence-service"
    assert payload["source_definition_id"] == "source-1"
    assert payload["source_item_ids"] == ["raw-1"]
