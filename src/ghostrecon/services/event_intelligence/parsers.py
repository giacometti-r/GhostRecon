from __future__ import annotations

import re
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from ghostrecon.models.db import (
    RawSourceItem,
    SourceDefinition,
)
from ghostrecon.services.source_registry import normalize_url


def _candidate_from_schema_org(
    event: dict[str, object],
    source: SourceDefinition,
    raw_item: RawSourceItem,
    series: str,
    timezone_hint: str | None,
) -> EventCandidate:
    start = _string(event.get("startDate"))
    end = _string(event.get("endDate"))
    start_time = normalize_event_time(start, timezone_hint)
    end_time = normalize_event_time(end, timezone_hint) if end else None
    location = event.get("location") if isinstance(event.get("location"), dict) else {}
    address = location.get("address") if isinstance(location.get("address"), dict) else {}
    geo = location.get("geo") if isinstance(location.get("geo"), dict) else {}
    attendance_mode = _string(event.get("eventAttendanceMode"))
    return EventCandidate(
        name=_string(event.get("name")) or raw_item.permitted_excerpt or source.name,
        event_series_key=series,
        external_id=_string(event.get("@id")) or raw_item.external_id,
        canonical_url=normalize_url(_string(event.get("url")) or raw_item.canonical_url),
        original_start=start,
        original_end=end,
        source_timezone=timezone_hint,
        iana_timezone=start_time.iana_timezone,
        timezone_status=start_time.status,
        starts_at_utc=start_time.value_utc,
        ends_at_utc=end_time.value_utc if end_time else None,
        event_format=_format_from_schema(attendance_mode),
        venue_name=_string(location.get("name")),
        street_address=_string(address.get("streetAddress")),
        city=_string(address.get("addressLocality")),
        region=_string(address.get("addressRegion")),
        postcode=_string(address.get("postalCode")),
        country=_country_code(address.get("addressCountry")),
        virtual_url=_string(event.get("url"))
        if attendance_mode and "online" in attendance_mode.lower()
        else None,
        latitude=_float(geo.get("latitude")),
        longitude=_float(geo.get("longitude")),
        topics=_keywords(event.get("keywords")),
        organizers=[_compact_org(item) for item in _as_list(event.get("organizer"))],
        confidence=85 if start_time.status == "resolved" else 65,
    )


def _candidate_from_ics(
    event: dict[str, object],
    source: SourceDefinition,
    raw_item: RawSourceItem,
    series: str,
    timezone_hint: str | None,
) -> EventCandidate:
    start = _string(event.get("DTSTART"))
    end = _string(event.get("DTEND"))
    start_time = normalize_event_time(_ics_datetime(start), timezone_hint)
    end_time = normalize_event_time(_ics_datetime(end), timezone_hint) if end else None
    location = _string(event.get("LOCATION"))
    return EventCandidate(
        name=_string(event.get("SUMMARY")) or source.name,
        event_series_key=series,
        external_id=_string(event.get("UID")) or raw_item.external_id,
        canonical_url=normalize_url(_string(event.get("URL")) or raw_item.canonical_url),
        original_start=start,
        original_end=end,
        source_timezone=timezone_hint,
        iana_timezone=start_time.iana_timezone,
        timezone_status=start_time.status,
        starts_at_utc=start_time.value_utc,
        ends_at_utc=end_time.value_utc if end_time else None,
        event_format="online" if location and location.lower().startswith("http") else "in-person",
        venue_name=None if location and location.lower().startswith("http") else location,
        virtual_url=location if location and location.lower().startswith("http") else None,
        confidence=80 if start_time.status == "resolved" else 60,
    )


def _candidate_from_feed(
    metadata: dict[str, object],
    source: SourceDefinition,
    raw_item: RawSourceItem,
    series: str,
    timezone_hint: str | None,
) -> EventCandidate:
    start_time = (
        normalize_event_time(raw_item.published_at.isoformat(), timezone_hint)
        if raw_item.published_at
        else None
    )
    return EventCandidate(
        name=_string(metadata.get("feed_title")) or source.name,
        event_series_key=series,
        external_id=raw_item.external_id,
        canonical_url=raw_item.canonical_url,
        original_start=raw_item.published_at.isoformat() if raw_item.published_at else None,
        source_timezone=timezone_hint,
        iana_timezone=start_time.iana_timezone if start_time else None,
        timezone_status=start_time.status if start_time else "missing",
        starts_at_utc=start_time.value_utc if start_time else None,
        event_format="unknown",
        confidence=55,
    )


def _candidate_from_page(
    metadata: dict[str, object],
    source: SourceDefinition,
    raw_item: RawSourceItem,
    series: str,
    timezone_hint: str | None,
) -> EventCandidate:
    title = _string(metadata.get("title")) or raw_item.permitted_excerpt or source.name
    return EventCandidate(
        name=title,
        event_series_key=series,
        external_id=raw_item.external_id,
        canonical_url=raw_item.canonical_url,
        source_timezone=timezone_hint,
        timezone_status="missing",
        event_format="unknown",
        confidence=40,
    )


def _participant_from_schema_node(
    item: object, participant_type: str
) -> ParticipantCandidate | None:
    if isinstance(item, str):
        name = item.strip()
        return (
            ParticipantCandidate(published_name=name, participant_type=participant_type)
            if name
            else None
        )
    if not isinstance(item, dict):
        return None
    name = _string(item.get("name"))
    if not name:
        return None
    affiliation = item.get("affiliation")
    org = (
        _string(affiliation.get("name"))
        if isinstance(affiliation, dict)
        else _string(item.get("worksFor"))
    )
    return ParticipantCandidate(
        published_name=name,
        source_participant_id=_string(item.get("@id")),
        organization=org,
        published_role=_string(item.get("jobTitle")) or participant_type,
        participant_type=participant_type,
        profile_url=_string(item.get("url")) or _string(item.get("sameAs")),
        resolution_confidence=80,
    )


def _parse_datetime(value: str) -> datetime | None:
    compact = value.strip()
    if not compact:
        return None
    if re.fullmatch(r"\d{8}", compact):
        parsed_date = datetime.strptime(compact, "%Y%m%d").date()
        return datetime.combine(parsed_date, time.min)
    if re.fullmatch(r"\d{8}T\d{6}Z", compact):
        return datetime.strptime(compact, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    if re.fullmatch(r"\d{8}T\d{6}", compact):
        return datetime.strptime(compact, "%Y%m%dT%H%M%S")
    try:
        return datetime.fromisoformat(compact.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(compact), time.min)
        except ValueError:
            return None


def _ics_datetime(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip()


def _is_ambiguous_local_time(value: datetime, zone: ZoneInfo) -> bool:
    first = value.replace(tzinfo=zone, fold=0).utcoffset()
    second = value.replace(tzinfo=zone, fold=1).utcoffset()
    return first != second


def _format_from_schema(attendance_mode: str | None) -> str:
    if not attendance_mode:
        return "unknown"
    lowered = attendance_mode.lower()
    if "mixed" in lowered:
        return "hybrid"
    if "online" in lowered:
        return "online"
    if "offline" in lowered:
        return "in-person"
    return "unknown"


def _as_list(value: object) -> list[object]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _keywords(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _compact_org(item: object) -> object:
    if isinstance(item, dict):
        return {key: item[key] for key in ("name", "url", "@id") if key in item}
    return item


def _country_code(value: object) -> str | None:
    text = _string(value)
    if not text:
        return None
    return text.upper() if len(text) == 2 else text[:2].upper()


def _string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return _string(value[0]) if value else None
    text = str(value).strip()
    return text or None


def _float(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown"


def _zone_key(value: object) -> str | None:
    return getattr(value, "key", None)


from .candidates import (  # noqa: E402  # noqa: E402
    EventCandidate,
    ParticipantCandidate,
    normalize_event_time,
)
