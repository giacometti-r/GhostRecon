from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from .identity import ParticipantReuseState


class EventFormat(StrEnum):
    IN_PERSON = "in-person"
    ONLINE = "online"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


def normalize_event_format_value(value: object) -> object:
    aliases = {
        "physical": EventFormat.IN_PERSON.value,
        "in_person": EventFormat.IN_PERSON.value,
        "in person": EventFormat.IN_PERSON.value,
        "virtual": EventFormat.ONLINE.value,
    }
    if isinstance(value, EventFormat):
        return value.value
    if isinstance(value, str):
        normalized = value.strip().lower()
        return aliases.get(normalized, normalized)
    return value


def _validate_absolute_http_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("must be an absolute http(s) URL")
    return normalized


def _validate_country_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if len(normalized) != 2 or not normalized.isalpha():
        raise ValueError("country must be a two-letter ISO 3166-1 alpha-2 code")
    return normalized


class EventCanonicalState(StrEnum):
    CANONICAL = "canonical"
    DUPLICATE = "duplicate"
    NEEDS_REVIEW = "needs_review"


class EventTimezoneStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    MISSING = "missing"


class EventParticipantType(StrEnum):
    SPEAKER = "speaker"
    SPONSOR = "sponsor"
    ORGANIZER = "organizer"
    ATTENDEE = "attendee"
    UNKNOWN = "unknown"


class CyberEventOut(BaseModel):
    id: str
    name: str
    event_series_key: str
    external_id: str | None = None
    canonical_url: str | None = None
    original_start: str | None = None
    original_end: str | None = None
    source_timezone: str | None = None
    iana_timezone: str | None = None
    timezone_status: EventTimezoneStatus = EventTimezoneStatus.RESOLVED
    starts_at_utc: datetime | None = None
    ends_at_utc: datetime | None = None
    event_format: EventFormat = EventFormat.UNKNOWN
    venue_name: str | None = None
    street_address: str | None = None
    city: str | None = None
    region: str | None = None
    postcode: str | None = None
    country: str | None = None
    virtual_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geocode_status: str = "not_required"
    geocode_provider: str | None = None
    geocode_display_name: str | None = None
    geocoded_at: datetime | None = None
    topics: list[object] = []
    organizers: list[object] = []
    confidence: int = Field(ge=0, le=100)
    canonical_state: EventCanonicalState = EventCanonicalState.CANONICAL
    source_definition_id: str | None = None
    source_item_ids: list[object] = []
    version: int = 1
    created_at: datetime
    updated_at: datetime

    @field_validator("event_format", mode="before")
    @classmethod
    def normalize_event_format(cls, value: object) -> object:
        return normalize_event_format_value(value)


class CyberEventList(BaseModel):
    events: list[CyberEventOut]


class EventParticipantOut(BaseModel):
    id: str
    cyber_event_id: str
    source_definition_id: str | None = None
    source_item_id: str | None = None
    source_participant_id: str | None = None
    published_name: str
    organization: str | None = None
    published_role: str | None = None
    participant_type: EventParticipantType = EventParticipantType.UNKNOWN
    profile_url: str | None = None
    reuse_state: ParticipantReuseState = ParticipantReuseState.UNKNOWN
    reuse_evidence: dict[str, object] = {}
    contact_extraction_allowed: bool
    crm_export_allowed: bool
    resolution_confidence: int = Field(ge=0, le=100)
    created_at: datetime
    updated_at: datetime


class EventParticipantList(BaseModel):
    participants: list[EventParticipantOut]


class EventParticipantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    published_name: str = Field(min_length=1, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    published_role: str | None = Field(default=None, max_length=255)
    participant_type: EventParticipantType = EventParticipantType.UNKNOWN
    profile_url: str | None = Field(default=None, max_length=2048)
    reuse_state: ParticipantReuseState = ParticipantReuseState.ALLOWED
    contact_extraction_allowed: bool = True
    crm_export_allowed: bool = False
    resolution_confidence: int = Field(default=70, ge=0, le=100)

    @field_validator("profile_url")
    @classmethod
    def validate_profile_url(cls, value: str | None) -> str | None:
        return _validate_absolute_http_url(value)


class ManualEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    event_series_key: str = Field(default="manual", min_length=1, max_length=128)
    canonical_url: str = Field(min_length=1, max_length=2048)
    original_start: str | None = None
    original_end: str | None = None
    source_timezone: str | None = None
    iana_timezone: str | None = None
    starts_at_utc: datetime
    ends_at_utc: datetime | None = None
    event_format: EventFormat
    venue_name: str | None = None
    street_address: str | None = None
    city: str | None = None
    region: str | None = None
    postcode: str | None = None
    country: str | None = None
    virtual_url: str | None = None
    topics: list[str] = []
    organizers: list[dict[str, object]] = []
    source_item_ids: list[str] = []
    confidence: int = Field(default=70, ge=0, le=100)

    @field_validator("event_format", mode="before")
    @classmethod
    def normalize_event_format(cls, value: object) -> object:
        return normalize_event_format_value(value)

    @field_validator("canonical_url", "virtual_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        return _validate_absolute_http_url(value)

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str | None) -> str | None:
        return _validate_country_code(value)


class EventUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    name: str | None = Field(default=None, min_length=1, max_length=255)
    event_series_key: str | None = Field(default=None, min_length=1, max_length=128)
    canonical_url: str | None = Field(default=None, max_length=2048)
    original_start: str | None = None
    original_end: str | None = None
    source_timezone: str | None = None
    iana_timezone: str | None = None
    starts_at_utc: datetime | None = None
    ends_at_utc: datetime | None = None
    event_format: EventFormat | None = None
    venue_name: str | None = None
    street_address: str | None = None
    city: str | None = None
    region: str | None = None
    postcode: str | None = None
    country: str | None = None
    virtual_url: str | None = None
    topics: list[str] | None = None
    organizers: list[dict[str, object]] | None = None
    source_item_ids: list[str] | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)

    @field_validator("event_format", mode="before")
    @classmethod
    def normalize_event_format(cls, value: object) -> object:
        return normalize_event_format_value(value)

    @field_validator("canonical_url", "virtual_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        return _validate_absolute_http_url(value)

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str | None) -> str | None:
        return _validate_country_code(value)
