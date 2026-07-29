from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class SecurityIncidentStatus(StrEnum):
    CANDIDATE = "candidate"
    CORROBORATED = "corroborated"
    REJECTED = "rejected"


class IncidentCanonicalState(StrEnum):
    CANONICAL = "canonical"
    DUPLICATE = "duplicate"
    NEEDS_REVIEW = "needs_review"


class CorroborationMethod(StrEnum):
    NONE = "none"
    AUTHORITATIVE_DISCLOSURE = "authoritative_disclosure"
    INDEPENDENT_SOURCES = "independent_sources"
    ANALYST_DECISION = "analyst_decision"


class WatchTargetType(StrEnum):
    COMPANY = "company"
    DOMAIN = "domain"
    INCIDENT = "incident"
    EVENT_SERIES = "event_series"
    TOPIC = "topic"


class NewsArticleOut(BaseModel):
    id: str
    canonical_url: str
    publisher: str | None = None
    title: str
    permitted_excerpt: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    original_language: str | None = None
    translated_title: str | None = None
    translation_metadata: dict[str, object] = {}
    content_hash: str
    syndication_cluster_key: str
    source_definition_id: str | None = None
    source_item_ids: list[object] = []
    created_at: datetime
    updated_at: datetime


class SecurityIncidentOut(BaseModel):
    id: str
    status: SecurityIncidentStatus = SecurityIncidentStatus.CANDIDATE
    title: str
    incident_group_key: str | None = None
    primary_affected_company: str | None = None
    primary_affected_domain: str | None = None
    affected_companies: list[object] = []
    affected_domains: list[object] = []
    incident_type: str | None = None
    attack_vector: str | None = None
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    geography: list[object] = []
    languages: list[object] = []
    confidence: int = Field(ge=0, le=100)
    evidence_article_ids: list[object] = []
    evidence_source_item_ids: list[object] = []
    evidence_families: list[object] = []
    evidence_urls: list[object] = []
    corroboration_method: CorroborationMethod = CorroborationMethod.NONE
    analyst_decision_ref: str | None = None
    canonical_state: IncidentCanonicalState = IncidentCanonicalState.CANONICAL
    source_definition_id: str | None = None
    source_item_ids: list[object] = []
    version: int
    created_at: datetime
    updated_at: datetime


class SecurityIncidentList(BaseModel):
    incidents: list[SecurityIncidentOut]


class ManualIncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=512)
    affected_companies: list[str] = []
    affected_domains: list[str] = []
    incident_type: str | None = None
    attack_vector: str | None = None
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    geography: list[str] = []
    languages: list[str] = []
    source_item_ids: list[str] = []
    evidence_urls: list[str] = []
    confidence: int = Field(default=70, ge=0, le=100)


class IncidentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    title: str | None = Field(default=None, min_length=1, max_length=512)
    affected_companies: list[str] | None = None
    affected_domains: list[str] | None = None
    incident_type: str | None = None
    attack_vector: str | None = None
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    geography: list[str] | None = None
    languages: list[str] | None = None
    source_item_ids: list[str] | None = None
    evidence_urls: list[str] | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)


class IncidentWatchPromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int


class WatchTargetOut(BaseModel):
    id: str
    target_type: WatchTargetType
    canonical_target_key: str
    display_name: str
    query_config: dict[str, object] = {}
    enabled: bool
    monitoring_enabled: bool = True
    monitoring_status: str = "not_run"
    last_monitored_at: datetime | None = None
    next_monitoring_at: datetime | None = None
    monitoring_error: str | None = None
    monitoring_summary: dict[str, object] = {}
    owner: str | None = None
    origin_incident_id: str | None = None
    created_by: str
    version: int
    created_at: datetime
    updated_at: datetime


class WatchTargetList(BaseModel):
    watch_targets: list[WatchTargetOut]


class WatchTargetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: WatchTargetType
    canonical_target_key: str
    display_name: str
    query_config: dict[str, object] = {}
    owner: str | None = None
    origin_incident_id: str | None = None


class WatchTargetPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    display_name: str | None = None
    query_config: dict[str, object] | None = None
    owner: str | None = None
    version: int
