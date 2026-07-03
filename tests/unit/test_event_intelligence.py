from datetime import UTC, datetime
from types import SimpleNamespace

from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.services.event_intelligence import (
    build_event_dedupe_key,
    candidates_from_raw_item,
    normalize_event_time,
    participant_eligibility,
    participants_from_raw_item,
)


def _source(**overrides):
    values = {
        "id": "source-1",
        "name": "Black Hat upcoming events",
        "query_scope": {"event_series_key": "black-hat"},
        "expected_timezone": "America/Los_Angeles",
        "participant_reuse_state": "unknown",
        "participant_reuse_evidence": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _raw(**overrides):
    values = {
        "id": "raw-1",
        "external_id": "evt-1",
        "canonical_url": "https://example.com/event",
        "source_timezone": None,
        "published_at": None,
        "permitted_excerpt": "Example event",
        "raw_metadata": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_normalize_event_time_preserves_source_and_converts_to_utc() -> None:
    normalized = normalize_event_time("2026-08-06T09:00:00", "America/Los_Angeles")

    assert normalized.original_value == "2026-08-06T09:00:00"
    assert normalized.iana_timezone == "America/Los_Angeles"
    assert normalized.value_utc == datetime(2026, 8, 6, 16, 0, tzinfo=UTC)
    assert normalized.status == "resolved"


def test_normalize_event_time_marks_missing_and_ambiguous_without_guessing() -> None:
    missing = normalize_event_time("2026-08-06T09:00:00", None)
    ambiguous = normalize_event_time("2026-11-01T01:30:00", "America/Los_Angeles")

    assert missing.value_utc is None
    assert missing.status == "missing"
    assert ambiguous.value_utc is None
    assert ambiguous.status == "ambiguous"


def test_schema_org_event_candidate_preserves_lineage_fields_and_dedupe_key() -> None:
    raw = _raw(
        raw_metadata={
            "schema_org_event": {
                "@id": "blackhat-2026",
                "@type": "Event",
                "name": "Black Hat USA 2026",
                "url": "https://blackhat.com/us-26/",
                "startDate": "2026-08-01T09:00:00",
                "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
                "location": {
                    "name": "Mandalay Bay",
                    "address": {
                        "addressLocality": "Las Vegas",
                        "addressRegion": "NV",
                        "addressCountry": "US",
                    },
                },
                "keywords": "security, research",
            }
        }
    )

    candidate = candidates_from_raw_item(_source(), raw)[0]

    assert candidate.name == "Black Hat USA 2026"
    assert candidate.event_series_key == "black-hat"
    assert candidate.event_format == "physical"
    assert candidate.country == "US"
    assert "security" in candidate.topics
    assert build_event_dedupe_key(candidate) == build_event_dedupe_key(candidate)


def test_schema_org_participants_are_published_only_and_policy_gated() -> None:
    raw = _raw(
        raw_metadata={
            "schema_org_event": {
                "performer": [
                    {
                        "@id": "speaker-1",
                        "name": "Ada Lovelace",
                        "jobTitle": "Researcher",
                        "affiliation": {"name": "Example Security"},
                        "url": "https://example.com/speakers/ada",
                    }
                ]
            }
        }
    )

    participants = participants_from_raw_item(_source(), raw)

    assert len(participants) == 1
    assert participants[0].published_name == "Ada Lovelace"
    assert participants[0].organization == "Example Security"
    assert participant_eligibility("allowed") == (True, True)
    assert participant_eligibility("unknown") == (False, False)
    assert participant_eligibility("prohibited") == (False, False)


def test_discovery_event_contracts_keep_source_lineage() -> None:
    event = new_event(
        event_name=EventName.CYBER_EVENT_DISCOVERED,
        aggregate_type="cyber_event",
        aggregate_id="event-1",
        source_service="event-intelligence-service",
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
        payload={"cyber_event_id": "event-1"},
    )

    payload = event.model_dump(mode="json")

    assert payload["event_name"] == "cyber_event.discovered"
    assert payload["producer"] == "event-intelligence-service"
    assert payload["source_definition_id"] == "source-1"
    assert payload["source_item_ids"] == ["raw-1"]
