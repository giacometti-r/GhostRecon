from enum import StrEnum


class SourceKind(StrEnum):
    EVENT = "event"
    INCIDENT = "incident"
    CRM = "crm"


class SourceAdapterType(StrEnum):
    HTTP_PAGE = "http_page"
    SCHEMA_ORG = "schema_org"
    ICS = "ics"
    RSS_ATOM = "rss_atom"
    SCHEDULED_QUERY = "scheduled_query"
    GDELT_DOC = "gdelt_doc"


class SourcePolicyState(StrEnum):
    ALLOWED = "allowed"
    UNKNOWN = "unknown"
    PROHIBITED = "prohibited"


class ContentStoragePolicy(StrEnum):
    METADATA_ONLY = "metadata_only"
    METADATA_EXCERPT = "metadata_excerpt"
    LICENSED_BODY = "licensed_body"


class SourceOperatingState(StrEnum):
    ENABLED = "enabled"
    PAUSED = "paused"
    DEGRADED = "degraded"


class SourceHealthStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class RawSourceParseStatus(StrEnum):
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class DuplicateState(StrEnum):
    CANONICAL = "canonical"
    DUPLICATE = "duplicate"
    QUARANTINED = "quarantined"
