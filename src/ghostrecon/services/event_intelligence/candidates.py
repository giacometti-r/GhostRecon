from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ghostrecon.models.db import (
    RawSourceItem,
    SourceDefinition,
)
from ghostrecon.services.source_registry import normalize_url

EVENT_SERVICE_NAME = "event-intelligence-service"


_ALLOWED_REUSE = "allowed"


@dataclass(frozen=True)
class NormalizedTime:
    original_value: str | None
    source_timezone: str | None
    iana_timezone: str | None
    value_utc: datetime | None
    status: str


@dataclass(frozen=True)
class EventCandidate:
    name: str
    event_series_key: str
    external_id: str | None = None
    canonical_url: str | None = None
    original_start: str | None = None
    original_end: str | None = None
    source_timezone: str | None = None
    iana_timezone: str | None = None
    timezone_status: str = "missing"
    starts_at_utc: datetime | None = None
    ends_at_utc: datetime | None = None
    event_format: str = "unknown"
    venue_name: str | None = None
    street_address: str | None = None
    city: str | None = None
    region: str | None = None
    postcode: str | None = None
    country: str | None = None
    virtual_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    topics: list[object] = field(default_factory=list)
    organizers: list[object] = field(default_factory=list)
    confidence: int = 50
    canonical_state: str = "canonical"


@dataclass(frozen=True)
class ParticipantCandidate:
    published_name: str
    source_participant_id: str | None = None
    organization: str | None = None
    published_role: str | None = None
    participant_type: str = "speaker"
    profile_url: str | None = None
    resolution_confidence: int = 70


def normalize_event_time(value: str | None, timezone_hint: str | None) -> NormalizedTime:
    if not value:
        return NormalizedTime(value, timezone_hint, None, None, "missing")

    parsed = _parse_datetime(value)
    if parsed is None:
        return NormalizedTime(value, timezone_hint, None, None, "ambiguous")

    if parsed.tzinfo is not None:
        return NormalizedTime(
            value,
            timezone_hint,
            _zone_key(parsed.tzinfo) or timezone_hint,
            parsed.astimezone(UTC),
            "resolved",
        )

    if not timezone_hint:
        return NormalizedTime(value, timezone_hint, None, None, "missing")

    try:
        zone = ZoneInfo(timezone_hint)
    except ZoneInfoNotFoundError:
        return NormalizedTime(value, timezone_hint, None, None, "ambiguous")

    if _is_ambiguous_local_time(parsed, zone):
        return NormalizedTime(value, timezone_hint, timezone_hint, None, "ambiguous")

    return NormalizedTime(
        value,
        timezone_hint,
        timezone_hint,
        parsed.replace(tzinfo=zone).astimezone(UTC),
        "resolved",
    )


def build_event_dedupe_key(candidate: EventCandidate) -> str:
    if candidate.external_id:
        identity = f"external:{candidate.event_series_key}:{candidate.external_id}"
    else:
        starts = (
            candidate.starts_at_utc.date().isoformat() if candidate.starts_at_utc else "unknown"
        )
        location = "|".join(
            part or ""
            for part in (
                candidate.country,
                candidate.region,
                candidate.city,
                candidate.event_format,
            )
        )
        identity = f"event:{candidate.event_series_key}:{_slug(candidate.name)}:{starts}:{location}"
    return f"cyber-event:{hashlib.sha256(identity.encode()).hexdigest()}"


def build_participant_dedupe_key(event_id: str, candidate: ParticipantCandidate) -> str:
    if candidate.source_participant_id:
        identity = f"external:{event_id}:{candidate.source_participant_id}"
    elif candidate.profile_url:
        identity = f"profile:{event_id}:{normalize_url(candidate.profile_url)}"
    else:
        identity = "|".join(
            [
                event_id,
                _slug(candidate.published_name),
                _slug(candidate.organization or ""),
                _slug(candidate.published_role or ""),
            ]
        )
    return f"event-participant:{hashlib.sha256(identity.encode()).hexdigest()}"


def participant_eligibility(reuse_state: str) -> tuple[bool, bool]:
    allowed = reuse_state == _ALLOWED_REUSE
    return allowed, allowed


def candidates_from_raw_item(
    source: SourceDefinition, raw_item: RawSourceItem
) -> list[EventCandidate]:
    metadata = raw_item.raw_metadata or {}
    series = str((source.query_scope or {}).get("event_series_key") or _slug(source.name))
    timezone_hint = raw_item.source_timezone or source.expected_timezone

    if isinstance(metadata.get("schema_org_event"), dict):
        return [
            _candidate_from_schema_org(
                metadata["schema_org_event"], source, raw_item, series, timezone_hint
            )
        ]
    if isinstance(metadata.get("ics_event"), dict):
        return [_candidate_from_ics(metadata["ics_event"], source, raw_item, series, timezone_hint)]
    if metadata.get("feed_title"):
        return [_candidate_from_feed(metadata, source, raw_item, series, timezone_hint)]
    return [_candidate_from_page(metadata, source, raw_item, series, timezone_hint)]


def participants_from_raw_item(
    source: SourceDefinition, raw_item: RawSourceItem
) -> list[ParticipantCandidate]:
    metadata = raw_item.raw_metadata or {}
    schema_event = metadata.get("schema_org_event")
    if not isinstance(schema_event, dict):
        return []

    participants: list[ParticipantCandidate] = []
    for field_name, participant_type in (
        ("performer", "speaker"),
        ("speaker", "speaker"),
        ("organizer", "organizer"),
        ("sponsor", "sponsor"),
        ("attendee", "attendee"),
    ):
        for item in _as_list(schema_event.get(field_name)):
            parsed = _participant_from_schema_node(item, participant_type)
            if parsed is not None:
                participants.append(parsed)
    return participants


from .parsers import (  # noqa: E402  # noqa: E402
    _as_list,
    _candidate_from_feed,
    _candidate_from_ics,
    _candidate_from_page,
    _candidate_from_schema_org,
    _is_ambiguous_local_time,
    _parse_datetime,
    _participant_from_schema_node,
    _slug,
    _zone_key,
)
